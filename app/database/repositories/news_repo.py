from datetime import date, datetime, timezone
import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import NewsArticle, NewsDigest


class NewsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_article_by_url(self, url: str) -> NewsArticle | None:
        return self.session.scalar(select(NewsArticle).where(NewsArticle.url == url))

    def get_article_by_hash(self, content_hash: str) -> NewsArticle | None:
        if not content_hash:
            return None
        return self.session.scalar(select(NewsArticle).where(NewsArticle.content_hash == content_hash))

    def save_article(
        self,
        category: str,
        title: str,
        url: str,
        source: str,
        published_at: datetime,
        summary: str = "",
        why_it_matters: str = "",
        content_hash: str | None = None,
        verification_status: str = "verified",
    ) -> NewsArticle:
        existing = self.get_article_by_url(url)
        if existing:
            existing.title = title
            existing.source = source
            existing.published_at = published_at
            if summary:
                existing.summary = summary
            if why_it_matters:
                existing.why_it_matters = why_it_matters
            if content_hash:
                existing.content_hash = content_hash
            existing.verification_status = verification_status
            self.session.commit()
            return existing

        article = NewsArticle(
            category=category,
            title=title,
            url=url,
            source=source,
            published_at=published_at,
            summary=summary,
            why_it_matters=why_it_matters,
            content_hash=content_hash,
            verification_status=verification_status,
            fetched_at=datetime.now(timezone.utc),
        )
        self.session.add(article)
        self.session.commit()
        return article

    def get_latest_articles(
        self,
        category: str | None = None,
        limit: int = 5,
        cutoff: datetime | None = None,
        verified_only: bool = True,
    ) -> list[NewsArticle]:
        stmt = select(NewsArticle)
        if category:
            stmt = stmt.where(NewsArticle.category == category)
        if verified_only:
            stmt = stmt.where(NewsArticle.verification_status == "verified")
        if cutoff:
            stmt = stmt.where(NewsArticle.published_at >= cutoff)
        stmt = stmt.order_by(NewsArticle.published_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def record_digest(self, user_id: int, day: date, category: str, article_ids: list[int]) -> NewsDigest:
        digest = NewsDigest(
            user_id=user_id,
            date=day,
            category=category,
            article_ids=json.dumps(article_ids),
            sent_at=datetime.now(timezone.utc),
        )
        self.session.add(digest)
        self.session.commit()
        return digest

    def has_sent_digest(self, user_id: int, day: date, category: str = "all") -> bool:
        stmt = select(NewsDigest).where(
            NewsDigest.user_id == user_id,
            NewsDigest.date == day,
            NewsDigest.category == category,
        )
        return self.session.scalar(stmt) is not None
