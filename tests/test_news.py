from datetime import datetime, timedelta, timezone
from app.bot.sanitizer import sanitize_zero_urls
from app.news.digest import format_single_news_item, split_digest_sections
from app.news.sources import CATEGORY_SOURCES
from app.news.verification import canonical_url, clean_html_text, is_fresh_article, split_title_and_source


def test_sources_contain_all_five_categories():
    assert "ai" in CATEGORY_SOURCES
    assert "world" in CATEGORY_SOURCES
    assert "cinema" in CATEGORY_SOURCES
    assert "telugu" in CATEGORY_SOURCES
    assert "india" in CATEGORY_SOURCES
    for cat, list_src in CATEGORY_SOURCES.items():
        assert len(list_src) >= 2


def test_canonical_url():
    raw = "https://example.com/article?utm_source=twitter&utm_medium=social&ref=homepage&id=123"
    clean = canonical_url(raw)
    assert "utm_source" not in clean
    assert "utm_medium" not in clean
    assert "ref=" not in clean
    assert "id=123" in clean


def test_split_title_and_source():
    raw = "DeepMind announces new AlphaFold model - Google Blog"
    headline, source = split_title_and_source(raw, fallback_source="RSS")
    assert headline == "DeepMind announces new AlphaFold model"
    assert source == "Google Blog"


def test_is_fresh_article():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    fresh_time = datetime.now(timezone.utc) - timedelta(hours=2)
    stale_time = datetime.now(timezone.utc) - timedelta(hours=48)
    assert is_fresh_article(fresh_time, cutoff) is True
    assert is_fresh_article(stale_time, cutoff) is False


def test_format_single_news_item_zero_urls():
    formatted = format_single_news_item(
        category="ai",
        index=1,
        headline="DeepMind Releases AlphaFold 3",
        what_happened="DeepMind has published research on AlphaFold 3 with major accuracy gains.",
        why_it_matters="Accelerates computational biology and drug discovery worldwide.",
        source="DeepMind Blog",
    )
    assert "<b>🤖 AI #1 — DeepMind Releases AlphaFold 3</b>" in formatted
    assert "<b>What happened:</b>" in formatted
    assert "• DeepMind has published research on AlphaFold 3 with major accuracy gains." in formatted
    assert "<b>Why it matters:</b>" in formatted
    assert "• Accelerates computational biology and drug discovery worldwide." in formatted
    assert "<b>Source:</b> DeepMind Blog" in formatted
    # Strict Zero-URL check
    assert "http://" not in formatted
    assert "https://" not in formatted
    assert "www." not in formatted
    assert "Link:" not in formatted



def test_sanitize_zero_urls_strips_all_links():
    dirty_text = (
        "🤖 AI #1 — New Model Launched\n\n"
        "What happened:\n"
        "Check out https://example.com/news for details or visit www.ai.com.\n"
        "Link: https://news.google.com/rss/articles/123\n"
        "Read more at [our blog](https://blog.example.com).\n"
        "<a href='https://spam.com'>Click here</a>\n"
        "Source: Reuters"
    )
    clean = sanitize_zero_urls(dirty_text)
    assert "https://" not in clean
    assert "http://" not in clean
    assert "www.ai.com" not in clean
    assert "Link:" not in clean
    assert "href=" not in clean
    assert "[our blog]" not in clean
    assert "Source: Reuters" in clean


def test_telugu_and_india_multi_bullet_formatting():
    from app.news.summarizer import _generate_topic_aware_fallback

    # Telugu AP News Item
    ap_item = {
        "title": "Supreme Court asks Andhra Pradesh high court to monitor child’s death probe after anti-malaria drug admin",
        "snippet": "",
        "source": "The Times of India",
    }
    fb_telugu = _generate_topic_aware_fallback(ap_item, "telugu")
    formatted_telugu = format_single_news_item(
        category="telugu",
        index=1,
        headline=ap_item["title"],
        what_happened=fb_telugu["what_happened"],
        why_it_matters=fb_telugu["why_it_matters"],
        source=ap_item["source"],
    )
    assert "<b>🟡 AP State (తెలుగు) #1 —" in formatted_telugu
    assert "<b>What happened:</b>" in formatted_telugu
    assert "<b>Why it matters:</b>" in formatted_telugu
    # Verify at least 2 bullets in what happened
    wh_section = formatted_telugu.split("<b>What happened:</b>")[1].split("<b>Why it matters:</b>")[0]
    assert wh_section.count("•") >= 2
    # Verify non-empty Telugu text
    assert any("\u0c00" <= c <= "\u0c7f" for c in formatted_telugu)

    # India National News Item
    in_item = {
        "title": "Voting in high-stakes bypolls in three States, one U.T. today",
        "snippet": "In Assam’s Nagaon, where the Lok Sabha byelection will be held, the fight is expected to be between the ruling BJP, the Congress and the AIUDF.",
        "source": "The Hindu National",
    }
    fb_india = _generate_topic_aware_fallback(in_item, "india")
    formatted_india = format_single_news_item(
        category="india",
        index=1,
        headline=in_item["title"],
        what_happened=fb_india["what_happened"],
        why_it_matters=fb_india["why_it_matters"],
        source=in_item["source"],
    )
    assert "<b>🇮🇳 India #1 —" in formatted_india
    assert "<b>What happened:</b>" in formatted_india
    assert "<b>Why it matters:</b>" in formatted_india
    wh_in_section = formatted_india.split("<b>What happened:</b>")[1].split("<b>Why it matters:</b>")[0]
    assert wh_in_section.count("•") >= 2

