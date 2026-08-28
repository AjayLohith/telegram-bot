from datetime import date, datetime, timezone
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models import DailyNewsDelivery, NewsArticle, NewsDigest


class DeliveryRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_delivery(
        self,
        user_id: int,
        day: date,
        digest_type: str = "production",
    ) -> DailyNewsDelivery | None:
        stmt = select(DailyNewsDelivery).where(
            DailyNewsDelivery.user_id == user_id,
            DailyNewsDelivery.date == day,
            DailyNewsDelivery.digest_type == digest_type,
        )
        return self.session.scalar(stmt)

    def get_or_create_delivery(
        self,
        user_id: int,
        day: date,
        scheduled_time: str = "07:00",
        digest_type: str = "production",
    ) -> tuple[DailyNewsDelivery, bool]:
        delivery = self.get_delivery(user_id, day, digest_type)
        if delivery:
            return delivery, False

        delivery = DailyNewsDelivery(
            user_id=user_id,
            date=day,
            scheduled_time=scheduled_time,
            started_at=datetime.now(timezone.utc),
            status="SCHEDULED",
            retry_count=0,
            digest_type=digest_type,
        )
        self.session.add(delivery)
        self.session.commit()
        return delivery, True

    def update_status(
        self,
        delivery_id: int,
        status: str,
        digest_hash: str | None = None,
        retry_count: int | None = None,
    ) -> None:
        delivery = self.session.get(DailyNewsDelivery, delivery_id)
        if delivery:
            delivery.status = status
            if status == "FETCHING" and not delivery.started_at:
                delivery.started_at = datetime.now(timezone.utc)
            if status == "SENT":
                delivery.completed_at = datetime.now(timezone.utc)
            if digest_hash is not None:
                delivery.digest_hash = digest_hash
            if retry_count is not None:
                delivery.retry_count = retry_count
            self.session.commit()

    def is_already_sent(self, user_id: int, day: date, digest_type: str = "production") -> bool:
        stmt = select(DailyNewsDelivery).where(
            DailyNewsDelivery.user_id == user_id,
            DailyNewsDelivery.date == day,
            DailyNewsDelivery.digest_type == digest_type,
            DailyNewsDelivery.status == "SENT",
        )
        return self.session.scalar(stmt) is not None

    def get_last_successful_7am_delivery(self) -> datetime | None:
        stmt = (
            select(DailyNewsDelivery.completed_at)
            .where(DailyNewsDelivery.status == "SENT", DailyNewsDelivery.digest_type == "production")
            .order_by(DailyNewsDelivery.completed_at.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def purge_bad_news_cache(self) -> int:
        """Deletes/invalidates previously cached articles and digests containing URLs or placeholder summaries."""
        res1 = self.session.execute(delete(NewsArticle))
        res2 = self.session.execute(delete(NewsDigest))
        self.session.commit()
        return (res1.rowcount or 0) + (res2.rowcount or 0)
