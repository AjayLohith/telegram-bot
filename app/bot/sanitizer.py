import re

_URL_PATTERN = re.compile(
    r"(?:https?://\S+|www\.\S+|\[.*?\]\(.*?\)|<a\s+href=.*?>.*?</a>|<a\s+href=[^>]*>)",
    re.IGNORECASE,
)
_LEFTOVER_LINK_LABEL = re.compile(r"^\s*(?:Link|Source URL|Read more|Article URL):\s*.*$", re.IGNORECASE | re.MULTILINE)


def sanitize_zero_urls(text: str) -> str:
    """Mandatory security/output filter that completely strips any URLs, hyperlinks,

    Markdown links, or HTML anchor tags from a Telegram message.
    """
    if not text:
        return ""

    # Remove any line starting with "Link: ..." or "Source URL: ..."
    cleaned = _LEFTOVER_LINK_LABEL.sub("", text)
    # Remove any raw URLs or markdown/html links
    cleaned = _URL_PATTERN.sub("", cleaned)
    # Collapse multiple blank lines
    lines = [line.rstrip() for line in cleaned.splitlines()]
    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()
