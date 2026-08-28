import re
from difflib import SequenceMatcher
from typing import Any

_NOISE_RE = re.compile(r"[^a-z0-9\s]+")


def normalize_headline(title: str) -> str:
    t = title.lower().strip()
    t = _NOISE_RE.sub(" ", t)
    return " ".join(t.split())


def are_headlines_duplicate(title1: str, title2: str, threshold: float = 0.80) -> bool:
    norm1 = normalize_headline(title1)
    norm2 = normalize_headline(title2)
    if not norm1 or not norm2:
        return False
    if norm1 == norm2:
        return True

    # Sequence Matcher ratio
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    if ratio >= threshold:
        return True

    # Token overlap check
    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())
    if len(tokens1) >= 4 and len(tokens2) >= 4:
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        if len(intersection) / len(union) >= 0.65:
            return True

    return False


def deduplicate_articles(articles: list[Any], threshold: float = 0.80) -> list[Any]:
    """Filters duplicate stories from a list of articles/dicts, preserving order (most recent first)."""
    kept = []
    seen_normalized: list[str] = []

    for article in articles:
        title = getattr(article, "title", None) or (article.get("title") if isinstance(article, dict) else "")
        norm = normalize_headline(title)
        if not norm:
            continue

        is_dup = False
        for seen in seen_normalized:
            if SequenceMatcher(None, norm, seen).ratio() >= threshold:
                is_dup = True
                break
            # token check
            s_tok = set(seen.split())
            n_tok = set(norm.split())
            if len(s_tok) >= 4 and len(n_tok) >= 4:
                if len(s_tok & n_tok) / len(s_tok | n_tok) >= 0.65:
                    is_dup = True
                    break

        if not is_dup:
            seen_normalized.append(norm)
            kept.append(article)

    return kept
