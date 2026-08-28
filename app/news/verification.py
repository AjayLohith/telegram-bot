import hashlib
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "gclid"}
_TITLE_SOURCE_SPLIT = re.compile(r"^(?P<headline>.+?)\s[-–—]\s(?P<pub>[^-–—]{2,50})$")


def canonical_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    parts = urlsplit(raw_url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if k.lower() not in _TRACKING_PARAMS]
    normalized_query = urlencode(sorted(query))
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, normalized_query, ""))


def compute_content_hash(title: str, summary: str) -> str:
    text = f"{title.strip().lower()}||{summary.strip().lower()}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_title_and_source(title: str, fallback_source: str = "RSS") -> tuple[str, str]:
    clean_t = clean_html_text(title)
    match = _TITLE_SOURCE_SPLIT.match(clean_t)
    if not match:
        return clean_t, fallback_source
    pub = match.group("pub").strip()
    headline = match.group("headline").strip()
    if 0 < len(pub.split()) <= 6 and not pub.endswith((".", "?", "!")):
        return headline, pub
    return clean_t, fallback_source


def clean_html_text(value: str, max_chars: int = 500) -> str:
    if not value:
        return ""
    for _ in range(3):
        decoded = unescape(value)
        if decoded == value:
            break
        value = decoded
    text = BeautifulSoup(value, "html.parser").get_text(" ")
    text = re.sub(r"<\s*/?\s*a\b[^>]*>|\[\s*/?\s*a\b[^]]*\]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:href|src)\s*=\s*(?:\"[^\"]*\"|'[^']*'|\S+)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:https?://|www\.)\S+", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split())[:max_chars]


def is_junk_summary(raw_summary: str) -> bool:
    if not raw_summary:
        return True
    return raw_summary.lower().count("<a ") >= 2


def is_fresh_article(published_at: datetime, cutoff: datetime) -> bool:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    return published_at >= cutoff
