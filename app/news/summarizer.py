import json
import logging
from dataclasses import dataclass
from typing import Any

from app.ai.providers import AIRouter, ProviderError
from app.news.verification import clean_html_text

logger = logging.getLogger(__name__)

CATEGORY_DEFAULT_WHY: dict[str, str] = {
    "ai": "Signals significant progress in AI models, architecture, chips, or developer tooling.",
    "world": "Affects regional geopolitical balance, environmental resilience, or geographic stability.",
    "anime": "Marks an official production update, broadcast timeline, or creative studio milestone.",
    "telugu": "Represents an important regional governance, economic, or cultural milestone for Andhra Pradesh and Telangana.",
    "india": "Impacts India's national development, technological advancement, economy, or public policy.",
}


@dataclass
class SummarizedItem:
    headline: str
    source: str
    url: str
    published_str: str
    what_happened: str
    why_it_matters: str
    category: str


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


async def summarize_category_articles(
    router_ai: AIRouter | None,
    category: str,
    items: list[dict[str, Any]],
    language: str = "en",
) -> list[dict[str, str]]:
    """Summarizes a batch of articles in a category.
    
    Returns a list of dicts with keys: 'what_happened', 'why_it_matters'.
    Falls back deterministically if router_ai is None or on error.
    """
    if not items:
        return []

    fallback_why = CATEGORY_DEFAULT_WHY.get(category, "Represents a notable development in this category.")

    if router_ai is None:
        return [_build_fallback(item, fallback_why) for item in items]

    prompt_lines = [
        f"You are a factual news intelligence assistant. Summarize the following {len(items)} {category.upper()} articles.",
        f"Language requested: {'Telugu' if language == 'te' else 'English'}.",
        "STRICT RULES:",
        "1. Never invent missing facts, names, numbers, or events.",
        "2. 'what_happened' must be 2-4 factual sentences strictly based on the headline and snippet.",
        "3. 'why_it_matters' must be 1 concise sentence explaining the significance.",
        "4. Return ONLY valid JSON format: {\"items\": [{\"what_happened\": \"...\", \"why_it_matters\": \"...\"}]}.",
        "5. Output must have exactly the same number of items in the same order.\n",
    ]

    for idx, itm in enumerate(items, 1):
        prompt_lines.append(f"Article #{idx}:")
        prompt_lines.append(f"Headline: {itm.get('title', '')}")
        prompt_lines.append(f"Source: {itm.get('source', '')}")
        snip = itm.get('snippet', '')
        if snip:
            prompt_lines.append(f"Snippet: {snip}")
        prompt_lines.append("")

    prompt = "\n".join(prompt_lines)

    try:
        raw_response = await router_ai.complete("digest_summary", prompt)
        clean_json = strip_code_fences(raw_response)
        data = json.loads(clean_json)
        res_items = data.get("items", [])
        if len(res_items) == len(items):
            validated = []
            for r, original in zip(res_items, items):
                wh = clean_html_text(r.get("what_happened", ""))
                wm = clean_html_text(r.get("why_it_matters", ""))
                if wh and wm:
                    validated.append({"what_happened": wh, "why_it_matters": wm})
                else:
                    validated.append(_build_fallback(original, fallback_why))
            return validated
    except (ProviderError, json.JSONDecodeError, KeyError, Exception) as err:
        logger.warning("AI summarization failed for category %s: %s. Using deterministic fallback.", category, err)

    return [_build_fallback(item, fallback_why) for item in items]


def _build_fallback(item: dict[str, Any], fallback_why: str) -> dict[str, str]:
    snippet = clean_html_text(item.get("snippet", ""))
    title = clean_html_text(item.get("title", ""))
    if snippet and len(snippet) >= 30:
        what_happened = snippet
    else:
        what_happened = f"New developments were reported regarding {title}."
    return {
        "what_happened": what_happened,
        "why_it_matters": fallback_why,
    }
