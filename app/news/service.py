import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging

import feedparser
import httpx
from sqlalchemy.orm import Session

from app.database.models import NewsArticle
from app.database.repositories.news_repo import NewsRepository
from app.news.sources import CATEGORY_SOURCES, SourceDefinition
from app.news.verification import canonical_url, compute_content_hash, is_junk_summary, split_title_and_source

logger = logging.getLogger(__name__)


class NewsService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = NewsRepository(session)

    async def refresh_all(self) -> list[NewsArticle]:
        tasks = [self.refresh_category(cat) for cat in CATEGORY_SOURCES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        saved = []
        for res in results:
            if isinstance(res, list):
                saved.extend(res)
        return saved

    async def _fetch_single_source(self, client: httpx.AsyncClient, src: SourceDefinition, category: str) -> list[dict]:
        try:
            response = await client.get(src.url)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
        except Exception as err:
            logger.debug("Failed to fetch RSS from %s (%s): %s", src.name, src.url, err)
            return []

        entries = []
        for entry in parsed.entries[:25]:
            raw_link = entry.get("link", "")
            url = canonical_url(raw_link)
            raw_title = entry.get("title", "")
            if not url or not raw_title:
                continue

            headline, extracted_source = split_title_and_source(raw_title, src.name)
            summary = _extract_summary(entry)
            pub_dt = _extract_published(entry) or datetime.now(timezone.utc)
            content_hash = compute_content_hash(headline, summary)

            entries.append({
                "category": category,
                "title": headline,
                "url": url,
                "source": extracted_source or src.name,
                "published_at": pub_dt,
                "summary": summary,
                "content_hash": content_hash,
            })
        return entries

    async def refresh_category(self, category: str) -> list[NewsArticle]:
        sources = CATEGORY_SOURCES.get(category, [])
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=headers) as client:
            fetch_tasks = [self._fetch_single_source(client, src, category) for src in sources]
            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        saved_articles: list[NewsArticle] = []
        for res in results:
            if isinstance(res, list):
                for item in res:
                    if self.repo.get_article_by_url(item["url"]) or self.repo.get_article_by_hash(item["content_hash"]):
                        continue
                    art = self.repo.save_article(
                        category=category,
                        title=item["title"],
                        url=item["url"],
                        source=item["source"],
                        published_at=item["published_at"],
                        summary=item["summary"],
                        content_hash=item["content_hash"],
                        verification_status="verified",
                    )
                    saved_articles.append(art)

        return saved_articles

    def get_category_articles(self, category: str, limit: int = 20) -> list[NewsArticle]:
        return self.repo.get_latest_articles(category=category, limit=limit)

    def latest(self, limit: int = 8, sources: list[str] | None = None) -> list[NewsArticle]:
        return self.repo.get_latest_articles(limit=limit)

    def get_sources_summary(self) -> dict[str, list[dict[str, str | int]]]:
        summary = {}
        for cat, sources in CATEGORY_SOURCES.items():
            summary[cat] = [{"name": s.name, "url": s.url, "tier": s.tier} for s in sources]
        return summary


def _extract_summary(entry) -> str:
    raw = entry.get("summary", entry.get("description", ""))
    if is_junk_summary(raw):
        return ""
    clean = " ".join(raw.replace("<p>", "").replace("</p>", "").replace("<br>", " ").split())
    return clean[:500]


def _extract_published(entry) -> datetime | None:
    val = entry.get("published") or entry.get("updated")
    if val:
        try:
            return parsedate_to_datetime(val).astimezone(timezone.utc)
        except Exception:
            pass
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    return None
