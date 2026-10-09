import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_NOISE_RE = re.compile(r"[^a-z0-9\s]+")
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "gclid"}


def canonicalize_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    parts = urlsplit(raw_url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if k.lower() not in _TRACKING_PARAMS]
    normalized_query = urlencode(sorted(query))
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, normalized_query, ""))


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

    # Token overlap check (Jaccard similarity on non-trivial words)
    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())
    if len(tokens1) >= 4 and len(tokens2) >= 4:
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        if len(intersection) / len(union) >= 0.60:
            return True

    return False


def deduplicate_articles(articles: list[Any], threshold: float = 0.80) -> list[Any]:
    """Filters duplicate stories from a list of articles/dicts by canonical URL and headline similarity."""
    kept = []
    seen_urls: set[str] = set()
    seen_headlines: list[str] = []

    for article in articles:
        url = getattr(article, "url", None) or (article.get("url") if isinstance(article, dict) else "")
        c_url = canonicalize_url(url)
        if c_url and c_url in seen_urls:
            continue

        title = getattr(article, "title", None) or (article.get("title") if isinstance(article, dict) else "")
        norm = normalize_headline(title)
        if not norm:
            continue

        is_dup = False
        for seen in seen_headlines:
            if are_headlines_duplicate(norm, seen, threshold=threshold):
                is_dup = True
                break

        if not is_dup:
            if c_url:
                seen_urls.add(c_url)
            seen_headlines.append(norm)
            kept.append(article)

    return kept


def deduplicate_cross_categories(category_articles_map: dict[str, list[Any]], threshold: float = 0.80) -> dict[str, list[Any]]:
    """Ensures that no story is duplicated across multiple categories in the same digest.
    
    Preserves stories in their primary category (e.g. AP stories stay in AP, not duplicated in National).
    """
    cleaned_map: dict[str, list[Any]] = {}
    globally_seen_urls: set[str] = set()
    globally_seen_headlines: list[str] = []

    for category, articles in category_articles_map.items():
        category_kept = []
        for article in articles:
            url = getattr(article, "url", None) or (article.get("url") if isinstance(article, dict) else "")
            c_url = canonicalize_url(url)
            if c_url and c_url in globally_seen_urls:
                continue

            title = getattr(article, "title", None) or (article.get("title") if isinstance(article, dict) else "")
            norm = normalize_headline(title)
            if not norm:
                continue

            is_dup = False
            for seen in globally_seen_headlines:
                if are_headlines_duplicate(norm, seen, threshold=threshold):
                    is_dup = True
                    break

            if not is_dup:
                if c_url:
                    globally_seen_urls.add(c_url)
                globally_seen_headlines.append(norm)
                category_kept.append(article)

        cleaned_map[category] = category_kept

    return cleaned_map
