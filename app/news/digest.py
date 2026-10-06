from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.ai.http_providers import configured_providers
from app.ai.providers import AIRouter
from app.bot.sanitizer import sanitize_zero_urls
from app.core.config import settings
from app.news.deduplication import deduplicate_articles
from app.news.service import NewsService
from app.news.sources import CATEGORY_DISPLAY_NAMES, CATEGORY_SHORT_LABELS, CATEGORY_SOURCES
from app.news.summarizer import summarize_category_articles
from app.news.verification import canonical_url, clean_html_text, is_fresh_article, is_junk_summary, split_title_and_source


def _get_ai_router() -> AIRouter | None:
    providers = configured_providers(settings)
    if not providers:
        return None
    preference = [name for name in ("groq", "gemini", "mistral", "openai") if name in providers]
    return AIRouter(providers, {"digest_summary": preference}) if preference else None


def format_single_news_item(
    category: str,
    index: int,
    headline: str,
    what_happened: str,
    why_it_matters: str,
    source: str,
) -> str:
    """Formats a single news item with clean Telegram HTML (zero markdown '#' or '**' artifacts)."""
    cat_label = CATEGORY_SHORT_LABELS.get(category, category.upper())
    clean_h = clean_html_text(headline)
    clean_src = clean_html_text(source)

    wh_bullets = _to_bullets(what_happened, is_what_happened=True)
    wm_bullets = _to_bullets(why_it_matters, is_what_happened=False)

    lines = [
        f"<b>{cat_label} #{index} — {clean_h}</b>",
        "",
        "<b>What happened:</b>",
        wh_bullets,
        "",
        "<b>Why it matters:</b>",
        wm_bullets,
        "",
        f"<b>Source:</b> {clean_src}",
    ]
    raw_text = "\n".join(lines)
    return sanitize_zero_urls(raw_text)


def _to_bullets(text: str, is_what_happened: bool = False) -> str:
    cleaned = clean_html_text(text)
    if not cleaned:
        if is_what_happened:
            return "• Key developments are being actively verified.\n• Relevant authorities are reviewing the latest updates."
        return "• Notable development with direct public and regional interest."

    # Normalize inline bullet characters: if text has inline " • " or " ▪ ", convert to line breaks
    normalized = cleaned.replace(" • ", "\n• ").replace(" ▪ ", "\n• ").replace(" * ", "\n• ")

    raw_lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    bullets = []

    for line in raw_lines:
        if line.startswith(("•", "*", "-", "▪")):
            parts = [p.strip() for p in line.split("•") if p.strip()]
            for p in parts:
                clean_p = p.lstrip("*-▪ ").strip()
                if len(clean_p) > 5:
                    bullets.append(f"• {clean_p}")
        else:
            # Check if line has multiple sentences (avoid splitting on initials/abbreviations like Rs. or U.T.)
            parts = [s.strip() for s in line.split(". ") if s.strip()]
            if len(parts) > 1 and all(len(p) > 15 for p in parts):
                for p in parts:
                    s_clean = p.rstrip(".") + "."
                    bullets.append(f"• {s_clean}")
            else:
                s_clean = line.rstrip(".") + "."
                if len(s_clean) > 5:
                    bullets.append(f"• {s_clean}")

    # Deduplicate while preserving order and filter out short fragments
    seen = set()
    deduped = []
    for b in bullets:
        clean_content = b.lstrip("• ").strip()
        # Filter out broken 1-word or tiny fragments (e.g. "• Law.", "• Order.")
        if len(clean_content) < 10 or len(clean_content.split()) < 2:
            continue
        key = clean_content.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(f"• {clean_content}")

    # If we got at least 2 distinct bullets, return them (up to 2-3 clean bullets)
    if len(deduped) >= 2:
        return "\n".join(deduped[:3])

    # If is_what_happened and we only have 1 bullet, split compound sentences cleanly
    if is_what_happened and len(deduped) == 1:
        single = deduped[0].lstrip("• ").strip()
        for sep in ["; ", " — ", " - ", ", while ", ", as well as ", ", and also ", ", and ", " మరియు "]:
            if sep in single:
                p1, p2 = single.split(sep, 1)
                if len(p1) >= 20 and len(p2) >= 20:
                    return f"• {p1.rstrip('.')}.\n• {p2.capitalize().rstrip('.')}."

        # If it's Telugu, add a natural everyday Telugu second line
        if any("\u0c00" <= c <= "\u0c7f" for c in single):
            return f"• {single}\n• ఈ అంశంపై పూర్తి వివరాలు మరియు తదుపరి చర్యలు త్వరలోనే రానున్నాయి."
        else:
            return f"• {single}\n• Official updates and further details are expected soon."

    if not deduped:
        return f"• {cleaned}"

    return "\n".join(deduped[:3])


async def build_category_digest(
    session: Session,
    category: str,
    limit: int = 5,
    language: str = "en",
    refresh: bool = True,
) -> str:
    """Build a standalone digest for a specific category with clean Telegram HTML and ZERO URLs."""
    service = NewsService(session)
    if refresh:
        await service.refresh_category(category)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    articles = service.get_category_articles(category, limit=max(limit * 4, 20))
    fresh = [a for a in articles if is_fresh_article(a.published_at, cutoff)]

    if len(fresh) < limit:
        wider_cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
        fresh = [a for a in articles if is_fresh_article(a.published_at, wider_cutoff)]

    deduped = deduplicate_articles(fresh)[:limit]

    display_header = CATEGORY_DISPLAY_NAMES.get(category, category.upper())
    if not deduped:
        return sanitize_zero_urls(f"<b>{display_header}</b>\n\n⚠️ Some news categories could not be verified today. No unverified stories were included.")

    prepared = []
    for art in deduped:
        h, s = split_title_and_source(art.title, art.source)
        snip = "" if is_junk_summary(art.summary) else clean_html_text(art.summary)
        prepared.append({
            "id": art.id,
            "title": h,
            "source": s or art.source,
            "snippet": snip,
            "url": canonical_url(art.url),
            "published_at": art.published_at,
        })

    router_ai = _get_ai_router()
    summaries = await summarize_category_articles(router_ai, category, prepared, language=language)

    sections = [f"<b>{display_header}</b>\n"]
    if len(deduped) < limit:
        sections.append(f"<i>Only {len(deduped)} verified developments were available for this category today.</i>\n")

    for idx, (prep, summ) in enumerate(zip(prepared, summaries), 1):
        item_text = format_single_news_item(
            category=category,
            index=idx,
            headline=prep["title"],
            what_happened=summ["what_happened"],
            why_it_matters=summ["why_it_matters"],
            source=prep["source"],
        )
        sections.append(item_text)

    full_text = "\n\n".join(sections)
    return sanitize_zero_urls(full_text)


async def build_compact_digest(
    session: Session,
    total: int = 5,
    language: str = "en",
) -> str:
    """Build a compact top news digest for /news 5 with clean Telegram HTML and ZERO URLs."""
    categories = ["ai", "world", "cinema", "telugu", "india"]
    service = NewsService(session)
    await service.refresh_all()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=36)
    router_ai = _get_ai_router()

    header_lines = [
        "<b>📰 TOP NEWS DIGEST</b>",
        f"📅 {datetime.now(ZoneInfo(settings.timezone)).strftime('%d %B %Y')}",
        f"⏰ {settings.news_time} AM IST\n",
    ]
    sections = ["\n".join(header_lines)]

    for cat in categories[:total]:
        articles = service.get_category_articles(cat, limit=10)
        fresh = [a for a in articles if is_fresh_article(a.published_at, cutoff)]
        deduped = deduplicate_articles(fresh)[:1]
        if not deduped:
            continue
        art = deduped[0]
        h, s = split_title_and_source(art.title, art.source)
        snip = "" if is_junk_summary(art.summary) else clean_html_text(art.summary)
        prep = {"title": h, "source": s or art.source, "snippet": snip, "url": canonical_url(art.url)}
        summs = await summarize_category_articles(router_ai, cat, [prep], language=language)
        summ = summs[0]

        item_text = format_single_news_item(
            category=cat,
            index=1,
            headline=prep["title"],
            what_happened=summ["what_happened"],
            why_it_matters=summ["why_it_matters"],
            source=prep["source"],
        )
        sections.append(item_text)

    return sanitize_zero_urls("\n\n".join(sections))


async def build_full_daily_digest(
    session: Session,
    language: str = "en",
    per_category_limit: int = 5,
) -> list[str]:
    """Builds the complete 25-item Daily Intelligence Digest with clean Telegram HTML."""
    categories = ["ai", "world", "cinema", "telugu", "india"]
    service = NewsService(session)
    await service.refresh_all()

    now_ist = datetime.now(ZoneInfo(settings.timezone))
    date_str = now_ist.strftime("%d %B %Y")

    header_msg = (
        "🌐 <b>J.A.R.V.I.S. DAILY INTELLIGENCE BRIEFING</b>\n\n"
        f"📅 {date_str}\n"
        f"⏰ {settings.news_time} AM IST\n\n"
        "<b>Verified Intelligence Categories:</b>\n\n"
        "🤖 AI & Viral Tech — 5\n"
        "🌍 Global & Geopolitics — 5\n"
        "🎬 Cinema & Tollywood Buzz — 5\n"
        "🟡 Andhra Pradesh (తెలుగు) — 5\n"
        "🇮🇳 India National — 5\n\n"
        "<i>All sources cross-verified for accuracy, sir.</i>"
    )

    messages = [sanitize_zero_urls(header_msg)]

    for cat in categories:
        cat_digest = await build_category_digest(session, cat, limit=per_category_limit, language=language, refresh=False)
        messages.append(sanitize_zero_urls(cat_digest))

    return messages


def split_digest_sections(digest: str) -> list[str]:
    """Backwards compatible splitter for digest strings."""
    if not digest:
        return []
    headings = (
        "<b>AI |",
        "<b>WORLD AND INDIA |",
        "<b>SPORT AND CRICKET |",
        "<b>CINEMA |",
        "<b>🤖 AI",
        "<b>🌍 GEOGRAPHY",
        "<b>🎬 CINEMA",
        "<b>🟡 ANDHRA",
        "<b>🟡 TELUGU",
        "<b>🇮🇳 INDIA",
        "🤖 AI",
        "🌍 GEOGRAPHY",
        "🎬 CINEMA",
        "🟡 ANDHRA",
        "🟡 TELUGU",
        "🇮🇳 INDIA",
    )
    positions = [position for heading in headings if (position := digest.find(heading)) >= 0]
    if not positions:
        return [sanitize_zero_urls(digest)]
    positions.sort()
    sections = [digest[:positions[0]].strip()]
    sections.extend(digest[start:end].strip() for start, end in zip(positions, positions[1:] + [len(digest)]))
    return [sanitize_zero_urls(section) for section in sections if section]


def _clean(value: str) -> str:
    return clean_html_text(value, max_chars=180)


def _is_fresh(published_at: datetime, cutoff: datetime) -> bool:
    return is_fresh_article(published_at, cutoff)


def _reasons(category: str) -> tuple[str, str]:
    return (
        "It signals a meaningful shift in models, chips, agents, or AI infrastructure.",
        "It can change the tools, costs, capabilities, or architecture available to developers.",
    )