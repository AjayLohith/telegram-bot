from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import DailySummary


class SummaryRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_daily_summary(self, user_id: int, day: date) -> DailySummary | None:
        stmt = select(DailySummary).where(
            DailySummary.user_id == user_id,
            DailySummary.date == day,
        )
        return self.session.scalar(stmt)

    def save_daily_summary(
        self,
        user_id: int,
        day: date,
        score: float,
        completion_pct: float,
        remarks: str | None = None,
        streak_days: int = 0,
    ) -> DailySummary:
        summary = self.get_daily_summary(user_id, day)
        if summary is None:
            summary = DailySummary(
                user_id=user_id,
                date=day,
                score=score,
                completion_percentage=completion_pct,
                remarks=remarks,
                streak_days=streak_days,
            )
            self.session.add(summary)
        else:
            summary.score = score
            summary.completion_percentage = completion_pct
            if remarks is not None:
                summary.remarks = remarks
            summary.streak_days = streak_days
        self.session.commit()
        return summary

    def get_history(self, user_id: int, limit: int = 30) -> list[DailySummary]:
        stmt = (
            select(DailySummary)
            .where(DailySummary.user_id == user_id)
            .order_by(DailySummary.date.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def get_all_summaries(self, user_id: int) -> list[DailySummary]:
        stmt = (
            select(DailySummary)
            .where(DailySummary.user_id == user_id)
            .order_by(DailySummary.date.asc())
        )
        return list(self.session.scalars(stmt))
