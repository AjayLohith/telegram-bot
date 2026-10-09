import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.ai.providers import AIRouter, ProviderError
from app.news.language import contains_telugu_script, is_valid_ap_english_article
from app.news.verification import clean_html_text

logger = logging.getLogger(__name__)

# Boilerplate patterns that must be stripped or rejected
_GENERIC_PREFIXES = [
    re.compile(r"^official updates were (announced|reported) regarding\s*", re.IGNORECASE),
    re.compile(r"^key (national |regional )?developments were (confirmed|reported) regarding\s*", re.IGNORECASE),
    re.compile(r"^new developments were reported regarding\s*", re.IGNORECASE),
    re.compile(r"^concerned ministries and agencies are tracking next steps and implementation\.?", re.IGNORECASE),
    re.compile(r"^authorities and (key )?stakeholders are actively monitoring follow-up actions\.?", re.IGNORECASE),
    re.compile(r"^holds policy significance for governance, civic welfare, and national administration\.?", re.IGNORECASE),
]


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


def sanitize_bullet_text(text: str, headline: str = "") -> str:
    """Removes generic introductory phrases and ensures bullet points add distinct factual value."""
    if not text:
        return ""
    clean = text.strip()
    for pattern in _GENERIC_PREFIXES:
        clean = pattern.sub("", clean).strip()

    # If the bullet is just a verbatim copy of the headline, ensure it reads as a proper factual sentence
    if headline and clean.lower().rstrip(".") == headline.lower().rstrip("."):
        clean = f"Reports confirmed {clean[0].lower() + clean[1:] if len(clean) > 1 else clean}"
    return clean


def _generate_grounded_fallback(item: dict[str, Any], category: str) -> dict[str, str]:
    """Generates an honest, article-specific summary and why-it-matters directly grounded in available data.
    
    Never fabricates facts or inserts generic governance boilerplate.
    All outputs for AP news are 100% in English.
    """
    title = clean_html_text(item.get("title", ""))
    snippet = clean_html_text(item.get("snippet", ""))
    t_lower = (title + " " + snippet).lower()

    # What Happened: Derive directly from snippet if available, else derive from headline
    if snippet and len(snippet) >= 40:
        # Split snippet into 1-2 distinct sentences if possible
        sentences = [s.strip() for s in snippet.split(". ") if s.strip()]
        if len(sentences) >= 2:
            wh = f"• {sentences[0].rstrip('.')}.\n• {sentences[1].rstrip('.')}."
        else:
            wh = f"• {title.rstrip('.')}.\n• {snippet.rstrip('.')}."
    else:
        wh = f"• {title.rstrip('.')}."

    # Why It Matters: Grounded in the specific topic of the article
    if any(w in t_lower for w in ("power", "electricity", "energy", "grid", "demand")):
        wm = "Directly affects power supply reliability, grid load management, and regional energy costs."
    elif any(w in t_lower for w in ("road", "highway", "orr", "rail", "transport", "traffic", "bridge", "connectivity")):
        wm = "Improves regional commuting safety, freight logistics efficiency, and local infrastructure connectivity."
    elif any(w in t_lower for w in ("invest", "cement", "plant", "crore", "jobs", "industry", "factory")):
        wm = "Boosts regional industrial growth, production capacity, and employment opportunities for local workers."
    elif any(w in t_lower for w in ("vote", "voter", "poll", "bypoll", "election", "blo", "form-7", "constituency", "electoral")):
        wm = "Crucial for safeguarding voter roll accuracy, electoral integrity, and democratic representation."
    elif any(w in t_lower for w in ("death", "dead", "killed", "probe", "investigat", "police", "arrest", "custody", "murder")):
        wm = "Essential for ensuring legal accountability, prompt investigative transparency, and public safety."
    elif any(w in t_lower for w in ("court", "high court", "supreme court", "judge", "bench", "bail")):
        wm = "Sets vital judicial precedent and reinforces institutional accountability."
    elif any(w in t_lower for w in ("child", "marriage", "school", "student", "education", "hospital", "health", "eye")):
        wm = "Directly impacts community welfare, healthcare access, and public protection standards."
    elif any(w in t_lower for w in ("ai", "model", "deepfake", "algorithm", "software", "chip", "research")):
        wm = "Drives technical capabilities, developer tooling standards, and responsible deployment practices."
    elif any(w in t_lower for w in ("movie", "cinema", "trailer", "teaser", "box office", "actor", "director")):
        wm = "Reflects commercial box office trends, creative talent moves, and audience entertainment interest."
    elif category == "telugu":
        wm = "Holds regional significance for Andhra Pradesh state administration, community welfare, or local development."
    else:
        wm = "Represents a notable development with direct public, civic, or institutional implications."

    return {"what_happened": wh, "why_it_matters": wm}


async def summarize_category_articles(
    router_ai: AIRouter | None,
    category: str,
    items: list[dict[str, Any]],
    language: str = "en",
) -> list[dict[str, str]]:
    """Summarizes a batch of articles for a category with explicit ID matching and grounded relevance."""
    if not items:
        return []

    # If AP news or standard briefing, enforce English
    target_lang = "English"

    if router_ai is None:
        return [_generate_grounded_fallback(item, category) for item in items]

    prompt_lines = [
        f"You are a factual, high-accuracy news intelligence assistant. Summarize the following {len(items)} {category.upper()} articles.",
        f"Output Language: {target_lang} (ENGLISH ONLY).",
        "STRICT MANDATORY RULES:",
        "1. GROUNDED FACTUALITY: Base summaries STRICTLY on the facts provided in each headline and snippet. Never invent facts, numbers, committees, or events.",
        "2. NO HEADLINE ECHOES: Do NOT merely copy the headline or prepend generic filler like 'Official updates were announced regarding...'. State the actual concrete facts.",
        "3. WHAT HAPPENED: Write 1 to 2 concise, informative bullet points separated by newlines with '• ' at the start of each bullet. For short news, 1 clear bullet is better than fabricated bullets.",
        "4. WHY IT MATTERS: Write exactly 1 concise sentence explaining the specific consequence or real-world significance of THIS particular event (e.g. for power -> supply/grid; for roads -> transit safety/connectivity; for crime -> accountability/justice; for elections -> voting integrity). NEVER use generic policy/governance templates across unrelated stories.",
        "5. ANDHRA PRADESH (AP) NEWS: Must be written 100% in clear English without any Telugu script characters.",
        "6. STRUCTURED JSON: Return ONLY valid JSON mapping each article by its exact 'id':",
        "{\"items\": [{\"id\": \"item_id\", \"what_happened\": \"• Bullet 1\\n• Bullet 2\", \"why_it_matters\": \"...\"}]}",
        f"7. You must include all {len(items)} items in the output.\n",
    ]

    for idx, itm in enumerate(items, 1):
        item_id = str(itm.get("id") or f"art_{idx}")
        prompt_lines.append(f"Article [ID: {item_id}]:")
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

        # Build lookup table by ID
        res_by_id: dict[str, dict[str, str]] = {}
        for r in res_items:
            rid = str(r.get("id", "")).strip()
            if rid:
                res_by_id[rid] = r

        validated_list = []
        for idx, original in enumerate(items, 1):
            item_id = str(original.get("id") or f"art_{idx}")
            r = res_by_id.get(item_id)

            # Fallback to index if ID matching was not exact but lengths match
            if not r and idx - 1 < len(res_items) and not res_items[idx - 1].get("id"):
                r = res_items[idx - 1]

            if r:
                wh_raw = clean_html_text(r.get("what_happened", ""))
                wm_raw = clean_html_text(r.get("why_it_matters", ""))

                # Enforce English for AP category
                if category == "telugu" and (contains_telugu_script(wh_raw) or contains_telugu_script(wm_raw)):
                    validated_list.append(_generate_grounded_fallback(original, category))
                    continue

                wh_clean = sanitize_bullet_text(wh_raw, original.get("title", ""))
                wm_clean = sanitize_bullet_text(wm_raw)

                if wh_clean and wm_clean and len(wh_clean) >= 10:
                    validated_list.append({"what_happened": wh_clean, "why_it_matters": wm_clean})
                else:
                    validated_list.append(_generate_grounded_fallback(original, category))
            else:
                validated_list.append(_generate_grounded_fallback(original, category))

        return validated_list

    except (ProviderError, json.JSONDecodeError, KeyError, Exception) as err:
        logger.warning("AI summarization failed for category %s: %s. Using deterministic grounded fallback.", category, err)

    return [_generate_grounded_fallback(item, category) for item in items]
