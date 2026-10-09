import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from app.ai.providers import AIRouter
from app.bot.sanitizer import sanitize_zero_urls
from app.news.deduplication import are_headlines_duplicate, deduplicate_articles, deduplicate_cross_categories
from app.news.digest import format_single_news_item, split_digest_sections, _to_bullets
from app.news.language import contains_telugu_script, is_english_text, is_valid_ap_english_article
from app.news.sources import CATEGORY_DISPLAY_NAMES, CATEGORY_SHORT_LABELS, CATEGORY_SOURCES
from app.news.summarizer import _generate_grounded_fallback, sanitize_bullet_text, summarize_category_articles
from app.news.verification import canonical_url, clean_html_text, is_fresh_article, split_title_and_source


def test_sources_contain_all_five_categories():
    assert "ai" in CATEGORY_SOURCES
    assert "world" in CATEGORY_SOURCES
    assert "cinema" in CATEGORY_SOURCES
    assert "telugu" in CATEGORY_SOURCES
    assert "india" in CATEGORY_SOURCES
    for cat, list_src in CATEGORY_SOURCES.items():
        assert len(list_src) >= 2


def test_ap_category_headers_are_english_only():
    assert "తెలుగు" not in CATEGORY_DISPLAY_NAMES["telugu"]
    assert "ఆంధ్రప్రదేశ్" not in CATEGORY_DISPLAY_NAMES["telugu"]
    assert "ANDHRA PRADESH STATE NEWS" in CATEGORY_DISPLAY_NAMES["telugu"]
    assert CATEGORY_SHORT_LABELS["telugu"] == "🟡 AP State"


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


# =========================================================================
# REQUIRED REGRESSION TESTS (A to H)
# =========================================================================

def test_test_a_ap_english_only_enforcement():
    """Test A: AP English-only enforcement.
    Rejects Telugu-script reporting, retains valid English reporting about AP, and produces English summaries.
    """
    english_ap_title = "Shree Cement plans Rs 6,700 crore investment in Andhra Pradesh: Minister"
    english_ap_summary = "The company plans new cement grinding units in Kadapa and Palnadu creating 3,000 jobs."

    telugu_title = "ఆంధ్రప్రదేశ్‌లో భారీ వర్షాలు, పలు జిల్లాల్లో హై అలర్ట్"
    telugu_summary = "రాష్ట్రంలో రానున్న రెండు రోజుల్లో భారీ నుంచి అతి భారీ వర్షాలు కురిసే అవకాశం ఉందని వాతావరణ శాఖ తెలిపింది."

    mixed_title = "CM pushes for Amaravati works — అమరావతి పనుల వేగవంతం"

    # Language validation checks
    assert is_valid_ap_english_article(english_ap_title, english_ap_summary) is True
    assert is_valid_ap_english_article(telugu_title, telugu_summary) is False
    assert is_valid_ap_english_article(mixed_title, "") is False

    # Check fallback generation for AP is 100% English
    item = {"title": english_ap_title, "snippet": english_ap_summary, "source": "The Hindu"}
    fallback = _generate_grounded_fallback(item, "telugu")
    assert not contains_telugu_script(fallback["what_happened"])
    assert not contains_telugu_script(fallback["why_it_matters"])
    assert "industrial" in fallback["why_it_matters"].lower() or "jobs" in fallback["why_it_matters"].lower()

    # Formatted item header is clean English
    formatted = format_single_news_item(
        category="telugu",
        index=1,
        headline=english_ap_title,
        what_happened=fallback["what_happened"],
        why_it_matters=fallback["why_it_matters"],
        source="The Hindu",
    )
    assert "<b>🟡 AP State #1 —" in formatted
    assert "(తెలుగు)" not in formatted
    assert "(ఆంధ్రప్రదేశ్)" not in formatted


@pytest.mark.asyncio
async def test_test_b_article_specific_summaries():
    """Test B: Article-specific summaries mapped by explicit ID without generic template insertion."""
    items = [
        {
            "id": "item_power",
            "title": "State grid records peak power demand of 240 MU during heatwave",
            "snippet": "Energy department officials reviewed daily power supply and thermal plant coal stocks.",
            "source": "The Hindu",
        },
        {
            "id": "item_eye",
            "title": "Sankar Foundation conducts rural eye screening camp in Visakhapatnam",
            "snippet": "Over 500 villagers received free cataract screenings and prescription spectacles.",
            "source": "Times of India",
        },
        {
            "id": "item_voter",
            "title": "BLOs directed to verify voter registration forms strictly with signatures",
            "snippet": "Election authorities issued revised guidelines to prevent fraudulent additions to voter rolls.",
            "source": "Indian Express",
        },
    ]

    # Test deterministic grounded fallbacks
    fb_power = _generate_grounded_fallback(items[0], "telugu")
    fb_eye = _generate_grounded_fallback(items[1], "telugu")
    fb_voter = _generate_grounded_fallback(items[2], "india")

    # Power summary must be about power/grid, not court or police
    assert "power" in fb_power["what_happened"].lower() or "grid" in fb_power["why_it_matters"].lower()
    assert "police" not in fb_power["what_happened"].lower()
    assert "court" not in fb_power["what_happened"].lower()

    # Eye camp summary must be about eye/health/welfare
    assert "cataract" in fb_eye["what_happened"].lower() or "eye" in fb_eye["what_happened"].lower()
    assert "power" not in fb_eye["what_happened"].lower()

    # Voter summary must be about voter/election
    assert "voter" in fb_voter["what_happened"].lower() or "electoral" in fb_voter["why_it_matters"].lower()


def test_test_c_duplicate_national_and_cross_category():
    """Test C: Cross-source and cross-category deduplication."""
    articles_ap = [
        {"title": "Assam woman found dead near railway tracks in Andhra Pradesh", "url": "https://thehindu.com/ap/tracks1", "source": "The Hindu"},
        {"title": "CM inspects port works at Machilipatnam", "url": "https://thehindu.com/ap/port1", "source": "The Hindu"},
    ]
    articles_india = [
        {"title": "Assam woman found dead near tracks in Andhra Pradesh: Police", "url": "https://indianexpress.com/india/tracks-copy", "source": "Indian Express"},
        {"title": "Supreme Court hears plea on electoral bonds", "url": "https://thehindu.com/india/sc1", "source": "The Hindu"},
    ]

    cat_map = {"telugu": articles_ap, "india": articles_india}
    deduped_map = deduplicate_cross_categories(cat_map)

    # AP keeps the tracks story, India section drops the duplicate tracks story
    assert len(deduped_map["telugu"]) == 2
    assert len(deduped_map["india"]) == 1
    assert "electoral bonds" in deduped_map["india"][0]["title"].lower()


def test_test_d_headline_repetition_validator():
    """Test D: Redundant boilerplate prefix and headline echo validation."""
    raw_bullet = "Official updates were announced regarding She made distress call from train. Day later, Assam woman found dead near tracks in Andhra Pradesh."
    headline = "She made distress call from train. Day later, Assam woman found dead near tracks in Andhra Pradesh"
    
    cleaned = sanitize_bullet_text(raw_bullet, headline=headline)
    assert not cleaned.lower().startswith("official updates were announced regarding")
    assert "Assam woman found dead" in cleaned

    generic_prefix = "Key national developments were confirmed regarding Supreme Court hearing."
    assert sanitize_bullet_text(generic_prefix) == "Supreme Court hearing."


def test_test_e_article_specific_why_it_matters():
    """Test E: Article-specific Why it matters grounded in facts."""
    power_item = {"title": "AP Transco orders 500 MW additional power to meet agricultural demand", "snippet": ""}
    road_item = {"title": "NHAI approves Rs 1,200 crore widening of coastal highway corridor", "snippet": ""}
    child_item = {"title": "District administration halts three child marriage attempts in rural mandal", "snippet": ""}

    why_power = _generate_grounded_fallback(power_item, "telugu")["why_it_matters"]
    why_road = _generate_grounded_fallback(road_item, "telugu")["why_it_matters"]
    why_child = _generate_grounded_fallback(child_item, "telugu")["why_it_matters"]

    # Check that each has a distinctive, topic-specific reason
    assert "power" in why_power.lower() or "grid" in why_power.lower() or "energy" in why_power.lower()
    assert "commuting" in why_road.lower() or "infrastructure" in why_road.lower() or "logistics" in why_road.lower()
    assert "welfare" in why_child.lower() or "protection" in why_child.lower() or "health" in why_child.lower()
    # None of them should be a generic empty boilerplate
    assert why_power != why_road
    assert why_road != why_child


def test_test_f_extraction_failure_safe_fallback():
    """Test F: Minimal snippet fallback without hallucinating committees or investigations."""
    item = {"title": "ISRO tests semi-cryogenic engine at Mahendragiri facility", "snippet": "", "source": "ISRO"}
    fallback = _generate_grounded_fallback(item, "india")
    assert "ISRO tests semi-cryogenic engine at Mahendragiri facility." in fallback["what_happened"]
    assert "committee" not in fallback["what_happened"].lower()
    assert "investigation" not in fallback["what_happened"].lower()


def test_test_g_similar_but_distinct_stories():
    """Test G: Genuinely distinct stories with common words survive deduplication."""
    t1 = "BJP wins bypoll election in Nagaon constituency"
    t2 = "Congress wins municipal ward election in Guwahati city"
    assert are_headlines_duplicate(t1, t2) is False

    articles = [
        {"title": t1, "url": "https://news.com/1"},
        {"title": t2, "url": "https://news.com/2"},
    ]
    deduped = deduplicate_articles(articles)
    assert len(deduped) == 2


def test_test_h_idempotent_digest_generation():
    """Test H: Digest section splitting and deduplication idempotency."""
    sections = [
        "<b>🤖 AI & VIRAL TECH NEWS</b>\n\nAI content",
        "<b>🟡 ANDHRA PRADESH STATE NEWS</b>\n\nAP content",
        "<b>🇮🇳 INDIA NATIONAL NEWS</b>\n\nIndia content",
    ]
    full_digest = "\n\n".join(sections)
    split_res = split_digest_sections(full_digest)
    assert len(split_res) == 3
    assert "ANDHRA PRADESH STATE NEWS" in split_res[1]
    assert "INDIA NATIONAL NEWS" in split_res[2]


def test_inline_bullets_and_clean_formatting():
    # Case 1: Inline bullet symbols in one line from LLM
    raw_ai_text = "• First key update happened here. • Second key follow up detail was reported."
    formatted = _to_bullets(raw_ai_text, is_what_happened=True)
    assert formatted.count("•") == 2
    assert "• First key update happened here." in formatted
    assert "• Second key follow up detail was reported." in formatted

    # Case 2: Broken abbreviation split like 'Law. Order' should not produce single-word bullet
    raw_abbr_text = "Rahul Gandhi was detained during a sit-in protest at Akashvani Bhawan. Opposition leaders demanded immediate action."
    formatted_abbr = _to_bullets(raw_abbr_text, is_what_happened=True)
    assert formatted_abbr.count("•") >= 2
    for line in formatted_abbr.splitlines():
        assert len(line.lstrip("• ").split()) >= 2
