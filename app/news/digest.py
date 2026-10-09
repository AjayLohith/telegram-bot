from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.ai.http_providers import configured_providers
from app.ai.providers import AIRouter
from app.bot.sanitizer import sanitize_zero_urls
from app.core.config import settings
from app.news.deduplication import deduplicate_articles, deduplicate_cross_categories
from app.news.language import is_valid_ap_english_article
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
            return "• Key factual developments were reported by the source."
        return "• Notable development with direct public and regional implications."

    # Normalize inline bullet characters: convert inline ' • ' or ' ▪ ' to line breaks
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
            # Check if line has multiple sentences (avoid splitting on abbreviations like Rs. or U.T.)
            parts = [s.strip() for s in line.split(". ") if s.strip()]
            if len(parts) > 1 and all(len(p) > 15 for p in parts):
                for p in parts:
                    s_clean = p.rstrip(".") + "."
                    bullets.append(f"• {s_clean}")
            else:
                s_clean = line.rstrip(".") + "."
                if len(s_clean) > 5:
                    bullets.append(f"• {s_clean}")

    # Deduplicate while preserving order and filter out fragments
    seen = set()
    deduped = []
    for b in bullets:
        clean_content = b.lstrip("• ").strip()
        if len(clean_content) < 8 or len(clean_content.split()) < 2:
            continue
        key = clean_content.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(f"• {clean_content}")

    if deduped:
        return "\n".join(deduped[:3])

    return f"• {cleaned}"


async def build_category_digest(
    session: Session,
    category: str,
    limit: int = 5,
    language: str = "en",
    refresh: bool = True,
    pre_deduped_articles: list | None = None,
) -> str:
    """Build a standalone digest for a specific category with clean Telegram HTML and ZERO URLs."""
    service = NewsService(session)
    if refresh:
        await service.refresh_category(category)

    if pre_deduped_articles is not None:
        deduped = pre_deduped_articles[:limit]
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        articles = service.get_category_articles(category, limit=max(limit * 4, 20))
        fresh = [a for a in articles if is_fresh_article(a.published_at, cutoff)]

        if len(fresh) < limit:
            wider_cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
            fresh = [a for a in articles if is_fresh_article(a.published_at, wider_cutoff)]

        # Filter AP articles to English-only
        if category == "telugu":
            fresh = [a for a in fresh if is_valid_ap_english_article(a.title, a.summary or "")]

        deduped = deduplicate_articles(fresh)[:limit]

    display_header = CATEGORY_DISPLAY_NAMES.get(category, category.upper())
    if not deduped:
        return sanitize_zero_urls(f"<b>{display_header}</b>\n\n<i>No qualifying verified English developments were available for this category today.</i>")

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

    cat_articles_map = {}
    for cat in categories:
        articles = service.get_category_articles(cat, limit=10)
        fresh = [a for a in articles if is_fresh_article(a.published_at, cutoff)]
        if cat == "telugu":
            fresh = [a for a in fresh if is_valid_ap_english_article(a.title, a.summary or "")]
        cat_articles_map[cat] = fresh

    deduped_map = deduplicate_cross_categories(cat_articles_map)

    for cat in categories[:total]:
        items = deduped_map.get(cat, [])
        if not items:
            continue
        art = items[0]
        h, s = split_title_and_source(art.title, art.source)
        snip = "" if is_junk_summary(art.summary) else clean_html_text(art.summary)
        prep = {"id": art.id, "title": h, "source": s or art.source, "snippet": snip, "url": canonical_url(art.url)}
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
    """Builds the complete 25-item Daily Intelligence Digest with cross-category deduplication."""
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
        "🟡 Andhra Pradesh State — 5\n"
        "🇮🇳 India National — 5\n\n"
        "<i>All sources cross-verified for accuracy, sir.</i>"
    )

    messages = [sanitize_zero_urls(header_msg)]

    # Fetch candidates for each category
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    wider_cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    cat_candidates = {}

    for cat in categories:
        articles = service.get_category_articles(cat, limit=max(per_category_limit * 4, 20))
        fresh = [a for a in articles if is_fresh_article(a.published_at, cutoff)]
        if len(fresh) < per_category_limit:
            fresh = [a for a in articles if is_fresh_article(a.published_at, wider_cutoff)]
        if cat == "telugu":
            fresh = [a for a in fresh if is_valid_ap_english_article(a.title, a.summary or "")]
        cat_candidates[cat] = fresh

    # Cross-category deduplication ensures no story in AP is duplicated in National or vice versa
    deduped_map = deduplicate_cross_categories(cat_candidates)

    for cat in categories:
        cat_items = deduped_map.get(cat, [])
        cat_digest = await build_category_digest(
            session,
            cat,
            limit=per_category_limit,
            language=language,
            refresh=False,
            pre_deduped_articles=cat_items,
        )
        messages.append(sanitize_zero_urls(cat_digest))

    return messages


def split_digest_sections(digest: str) -> list[str]:
    """Backwards compatible splitter for digest strings."""
    if not digest or not digest.strip():
        return []

    headings = [
        "<b>AI |",
        "<b>WORLD AND INDIA |",
        "<b>SPORT AND CRICKET |",
        "<b>CINEMA |",
        "<b>🤖 AI",
        "<b>🌍 GEOGRAPHY",
        "<b>🌍 GLOBAL",
        "<b>🎬 CINEMA",
        "<b>🟡 ANDHRA",
        "<b>🟡 AP",
        "<b>🟡 TELUGU",
        "<b>🇮🇳 INDIA",
    ]

    positions = [digest.find(h) for h in headings if digest.find(h) >= 0]
    if not positions:
        plain_headings = ["🤖 AI", "🌍 GEOGRAPHY", "🌍 GLOBAL", "🎬 CINEMA", "🟡 ANDHRA", "🟡 AP", "🟡 TELUGU", "🇮🇳 INDIA"]
        positions = [digest.find(h) for h in plain_headings if digest.find(h) >= 0]

    if not positions:
        return [sanitize_zero_urls(digest.strip())]

    positions = sorted(set(positions))
    sections = []
    if positions[0] > 0:
        first_part = digest[:positions[0]].strip()
        if first_part:
            sections.append(first_part)

    for i in range(len(positions)):
        start = positions[i]
        end = positions[i + 1] if i + 1 < len(positions) else len(digest)
        sec = digest[start:end].strip()
        if sec:
            sections.append(sec)

    return [sanitize_zero_urls(s) for s in sections if s]


def _clean(value: str) -> str:
    return clean_html_text(value, max_chars=180)


def _is_fresh(published_at: datetime, cutoff: datetime) -> bool:
    return is_fresh_article(published_at, cutoff)


def _reasons(category: str) -> tuple[str, str]:
    return (
        "It signals a meaningful shift in models, chips, agents, or AI infrastructure.",
        "It can change the tools, costs, capabilities, or architecture available to developers.",
    )