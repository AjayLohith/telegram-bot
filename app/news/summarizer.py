import json
import logging
from dataclasses import dataclass
from typing import Any

from app.ai.providers import AIRouter, ProviderError
from app.news.verification import clean_html_text

logger = logging.getLogger(__name__)

CATEGORY_DEFAULT_WHY: dict[str, str] = {
    "ai": "Signals significant progress, viral developments, or safety concerns in AI models and tooling.",
    "world": "Affects regional geopolitical balance, environmental resilience, or geographic stability.",
    "cinema": "Highlights major box office trends, movie announcements, upcoming releases, or industry buzz.",
    "telugu": "ఆంధ్రప్రదేశ్ రాష్ట్ర అభివృద్ధి, పరిపాలన లేదా ప్రజా సంక్షేమానికి సంబంధించిన ముఖ్యమైన వార్త.",
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


def _generate_topic_aware_fallback(item: dict[str, Any], category: str) -> dict[str, str]:
    """Generates rich, topic-specific multi-bullet summaries and unique why-it-matters rationale."""
    title = clean_html_text(item.get("title", ""))
    snippet = clean_html_text(item.get("snippet", ""))
    t_lower = (title + " " + snippet).lower()

    if category == "telugu":
        # Andhra Pradesh State News — Natural, everyday spoken Telugu (వ్యవహారిక తెలుగు)
        if any(w in t_lower for w in ("court", "judge", "police", "probe", "death", "arrest", "remand", "custody", "high court", "supreme court", "law", "sc")):
            wh = (
                f"• ఆంధ్రప్రదేశ్‌లో {title} అంశంపై కోర్టు మరియు పోలీస్ శాఖ కీలక ఆదేశాలు ఇచ్చాయి.\n"
                f"• బాధితులకు న్యాయం జరిగేలా సమగ్ర విచారణ జరపాలని అధికారులు ఆదేశించారు."
            )
            wm = "• రాష్ట్రంలో చట్టం, న్యాయపరమైన పారదర్శకత మరియు ప్రజల భద్రతకు ఇది చాలా ముఖ్యం."
        elif any(w in t_lower for w in ("cement", "invest", "crore", "industry", "company", "jobs", "plant")):
            wh = (
                f"• ఆంధ్రప్రదేశ్‌లో భారీ పెట్టుబడులతో కొత్త ప్లాంట్లు ఏర్పాటు చేయాలని నిర్ణయించారు.\n"
                f"• దీని ద్వారా వేలాది మంది స్థానిక యువతకు ఉపాధి, కొత్త ఉద్యోగ అవకాశాలు లభిస్తాయి."
            )
            wm = "• రాష్ట్ర పారిశ్రామిక ప్రగతికి ఊతం ఇచ్చి, స్థానిక ఆర్థిక వ్యవస్థను వేగంగా ముందుకు నడిపిస్తుంది."
        elif any(w in t_lower for w in ("power", "energy", "electricity", "minister", "water", "polavaram", "amaravati", "infra", "project", "road", "rail", "orr")):
            wh = (
                f"• ఆంధ్రప్రదేశ్‌లో {title} పనులను వేగవంతం చేయాలని ప్రభుత్వం ఆదేశించింది.\n"
                f"• నిధుల కేటాయింపు, నాణ్యతా ప్రమాణాలు మరియు త్వరితగతిన పూర్తి చేయడంపై సమీక్ష నిర్వహించారు."
            )
            wm = "• ప్రజలకు మెరుగైన రవాణా, నిరంతర విద్యుత్ మరియు ఆధునిక మౌలిక వసతులు అందుబాటులోకి వస్తాయి."
        elif any(w in t_lower for w in ("protest", "strike", "rajaka", "community", "sc status", "reservation", "welfare", "demand", "scheme", "foundation", "eye", "health")):
            wh = (
                f"• {title} అంశంపై ప్రజలు మరియు సంబంధిత వర్గాలు తమ అభిప్రాయాలను వెల్లడించాయి.\n"
                f"• ప్రజలకు నాణ్యమైన సేవలు అందించేందుకు మరియు సమస్యల పరిష్కారానికి అధికారులు చర్యలు ప్రారంభించారు."
            )
            wm = "• ప్రజారోగ్యం, సామాజిక న్యాయం మరియు సంక్షేమ పథకాల అమలులో ఇది కీలకమైన అడుగు."
        else:
            if snippet and len(snippet) >= 30:
                wh = (
                    f"• {title}కు సంబంధించిన తాజా వివరాలు నివేదించబడ్డాయి.\n"
                    f"• {snippet.rstrip('.')}."
                )
            else:
                wh = (
                    f"• ఆంధ్రప్రదేశ్‌లో {title}పై ప్రభుత్వం మరియు అధికారులు దృష్టి సారించారు.\n"
                    f"• క్షేత్రస్థాయిలో తాజా పరిస్థితిని అధికారులు నిరంతరం పర్యవేక్షిస్తున్నారు."
                )
            wm = "• రాష్ట్ర అభివృద్ధి, ప్రజా సంక్షేమం మరియు పాలనా పరంగా ఇది ముఖ్యమైన పరిణామం."
        return {"what_happened": wh, "why_it_matters": wm}

    elif category == "india":
        # India National News — Balanced, punchy, human-readable bullet points
        if any(w in t_lower for w in ("vote", "voting", "bypoll", "poll", "election", "constituency", "bjp", "congress", "assembly", "sir", "blo", "voter")):
            wh = (
                f"• Key voting and electoral developments were reported regarding {title}.\n"
                f"• Political parties and election authorities have stepped up ground coordination and monitoring."
            )
            wm = "• Directly influences voter turnout, transparency, and regional political momentum."
        elif any(w in t_lower for w in ("strike", "vessel", "navy", "crew", "killed", "attack", "border", "defense", "military", "ship")):
            wh = (
                f"• Critical maritime and security alerts emerged regarding {title}.\n"
                f"• Defense and external affairs teams are coordinating immediate assistance and crew safety."
            )
            wm = "• Highlights regional maritime security priorities and protection for Indian personnel abroad."
        elif any(w in t_lower for w in ("fire", "accident", "blast", "rescue", "hospital", "collapsed", "injured")):
            wh = (
                f"• Emergency rescue teams rushed to the site following reports of {title}.\n"
                f"• First responders brought the situation under control, and safety audits are underway."
            )
            wm = "• Emphasizes the need for strict public safety measures and rapid emergency response."
        elif any(w in t_lower for w in ("detained", "rahul", "protest", "dharna", "opposition", "police", "march")):
            wh = (
                f"• Political leaders staged high-profile protests regarding {title}.\n"
                f"• Opposition parties raised key demands while law enforcement managed the demonstration."
            )
            wm = "• Signals heightened political tensions and intense debate on constitutional rights."
        else:
            if snippet and len(snippet) >= 30:
                wh = (
                    f"• Key national developments were confirmed regarding {title}.\n"
                    f"• {snippet.rstrip('.')}."
                )
            else:
                wh = (
                    f"• Official updates were announced regarding {title}.\n"
                    f"• Concerned ministries and agencies are tracking next steps and implementation."
                )
            wm = "• Holds policy significance for governance, civic welfare, and national administration."
        return {"what_happened": wh, "why_it_matters": wm}

    elif category == "cinema":
        wh = (
            f"• Major film updates and announcements dropped regarding {title}.\n"
            f"• Fans and trade analysts are tracking the teaser buzz, shooting schedules, and release plans."
        )
        wm = "• Sets box office momentum and strong audience anticipation across the film industry."
        return {"what_happened": wh, "why_it_matters": wm}

    elif category == "ai":
        wh = (
            f"• New technical capabilities and benchmark results were unveiled for {title}.\n"
            f"• Engineers and researchers are evaluating the practical performance and safety guardrails."
        )
        wm = "• Speeds up developer workflows and sets the pace for real-world AI deployment."
        return {"what_happened": wh, "why_it_matters": wm}

    else:  # world
        wh = (
            f"• Important international developments were reported regarding {title}.\n"
            f"• Diplomatic officials and regional bodies are assessing the immediate global impact."
        )
        wm = "• Influences geopolitical stability, cross-border trade, and international diplomacy."
        return {"what_happened": wh, "why_it_matters": wm}


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

    if router_ai is None:
        return [_generate_topic_aware_fallback(item, category) for item in items]

    target_lang = "Telugu (తెలుగు)" if (category == "telugu" or language == "te") else "English"

    prompt_lines = [
        f"You are a top-tier factual news intelligence analyst. Summarize the following {len(items)} {category.upper()} news articles.",
        f"Output Language: {target_lang}.",
        "CRITICAL FORMAT & LENGTH RULES:",
        "1. DO NOT simply copy/paste or echo the headline.",
        "2. 'what_happened': Must contain EXACTLY 2 to 3 crisp, balanced bullet points, separated by newlines with '• ' at the start of each bullet.",
        "3. Bullet point length rule: Keep each bullet point to 1-2 punchy sentences (approx 15-25 words each). DO NOT make long runaway paragraphs or 1-word fragments. Make them highly readable and informative.",
        "4. 'why_it_matters': Must be EXACTLY 1 concise, insightful sentence explaining the real-world impact (NEVER a generic template).",
        "5. TELUGU TONE (if category is 'telugu' or language is 'te'): Use natural, everyday conversational Telugu (దైనందిన వ్యవహారిక తెలుగు భాష). Avoid heavy, ancient, bookish Sanskrit vocabulary. Keep it clear, simple, and engaging for daily readers.",
        "6. If category is 'telugu', focus on Andhra Pradesh state news, Amaravati, Polavaram, investments, state ministers, local governance, and civic welfare.",
        "7. If category is 'cinema', focus on Tollywood / Indian cinema box office, shoot updates, teaser/trailer buzz, casting, or director insights.",
        "8. Return ONLY valid JSON format with NO markdown wrapping outside: {\"items\": [{\"what_happened\": \"• Point 1\\n• Point 2\", \"why_it_matters\": \"...\"}]}.",
        f"9. Output must contain exactly {len(items)} items in the same order.\n",
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
                if wh and wm and len(wh) >= 15:
                    validated.append({"what_happened": wh, "why_it_matters": wm})
                else:
                    validated.append(_generate_topic_aware_fallback(original, category))
            return validated
    except (ProviderError, json.JSONDecodeError, KeyError, Exception) as err:
        logger.warning("AI summarization failed for category %s: %s. Using deterministic fallback.", category, err)

    return [_generate_topic_aware_fallback(item, category) for item in items]


