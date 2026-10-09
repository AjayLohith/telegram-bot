import re
from typing import Any

# Telugu script Unicode range: \u0C00-\u0C7F
_TELUGU_SCRIPT_RE = re.compile(r"[\u0C00-\u0C7F]")
_LATIN_WORD_RE = re.compile(r"[a-zA-Z]{2,}")


def contains_telugu_script(text: str) -> bool:
    """Returns True if the text contains any Telugu script Unicode characters."""
    if not text:
        return False
    return bool(_TELUGU_SCRIPT_RE.search(text))


def is_english_text(text: str, max_telugu_ratio: float = 0.05) -> bool:
    """Validates if text is primarily English.
    
    Allows proper nouns, location names (e.g. Amaravati, Visakhapatnam, Polavaram),
    and quotations in Latin script, but rejects Telugu script reporting.
    """
    if not text or not text.strip():
        return False

    clean = text.strip()
    telugu_chars = len(_TELUGU_SCRIPT_RE.findall(clean))
    total_chars = len(clean)

    if total_chars > 0 and (telugu_chars / total_chars) > max_telugu_ratio:
        return False

    # Ensure there are sufficient Latin/English words
    latin_words = _LATIN_WORD_RE.findall(clean)
    if not latin_words and total_chars > 10:
        return False

    return True


def is_valid_ap_english_article(title: str, summary: str = "", source: str = "") -> bool:
    """Strictly validates that an Andhra Pradesh news article is in English.
    
    Rejects Telugu-script headlines, Telugu descriptions, or mixed-script reporting.
    Accepts legitimate English reporting about Andhra Pradesh from state/national publications.
    """
    if contains_telugu_script(title):
        return False
    if contains_telugu_script(summary):
        return False

    if not is_english_text(title):
        return False

    if summary and not is_english_text(summary):
        return False

    return True
