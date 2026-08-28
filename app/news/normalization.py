from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class NormalizedArticle:
    url: str
    title: str
    content_hash: str


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith("utm_")]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def normalize_article(url: str, title: str, summary: str = "") -> NormalizedArticle:
    canonical = canonical_url(url)
    normalized_title = " ".join(title.split()).strip()
    content_hash = sha256(f"{normalized_title.lower()}\n{summary.strip().lower()}".encode()).hexdigest()
    return NormalizedArticle(canonical, normalized_title, content_hash)
