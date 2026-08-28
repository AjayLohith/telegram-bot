from datetime import date, datetime, timezone
import json
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    language: Mapped[str] = mapped_column(String(20), default="en")  # en, te, bilingual
    
    # Configurable schedule times
    news_time: Mapped[str] = mapped_column(String(10), default="08:30")
    morning_time: Mapped[str] = mapped_column(String(10), default="08:00")
    video_time: Mapped[str] = mapped_column(String(10), default="10:00")
    study_time: Mapped[str] = mapped_column(String(10), default="14:00")
    exercise_time: Mapped[str] = mapped_column(String(10), default="18:00")
    eod_time: Mapped[str] = mapped_column(String(10), default="21:00")
    
    # Feature flags & thresholds
    streak_threshold: Mapped[float] = mapped_column(Float, default=70.0)
    breaking_news_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    missed_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    morning_combined_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    task_type: Mapped[str] = mapped_column(String(40), default="custom")  # video, study, exercise, custom
    target_value: Mapped[float] = mapped_column(Float, default=1.0)
    target_unit: Mapped[str] = mapped_column(String(40), default="count")  # hours, minutes, count, done
    points: Mapped[float] = mapped_column(Float, default=20.0)
    reminder_time: Mapped[str] = mapped_column(String(10), default="10:00")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped["User"] = relationship(back_populates="tasks")
    completions: Mapped[list["TaskCompletion"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskCompletion(Base):
    __tablename__ = "task_completions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")  # completed, skipped, pending, in_progress
    actual_value: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string for extra fields
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship(back_populates="completions")

    def get_details_dict(self) -> dict:
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except Exception:
            return {}

    def set_details_dict(self, data: dict) -> None:
        self.details = json.dumps(data)


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    completion_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), index=True)  # ai, world, anime, telugu, india
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(120), default="RSS")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(String(30), default="verified")  # verified, rejected


class NewsDigest(Base):
    __tablename__ = "news_digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(50), default="all")
    article_ids: Mapped[str] = mapped_column(Text)  # JSON array of article IDs
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    task_name: Mapped[str] = mapped_column(String(255))
    reminder_time: Mapped[str] = mapped_column(String(10))  # 24h format HH:MM, e.g. "20:30"
    display_time: Mapped[str] = mapped_column(String(20), default="")  # 12h format, e.g. "8:30 PM"
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    recurrence: Mapped[str] = mapped_column(String(40), default="DAILY")
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_trigger_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DailyNewsDelivery(Base):
    __tablename__ = "daily_news_delivery"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    scheduled_time: Mapped[str] = mapped_column(String(10), default="07:00")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="SCHEDULED")  # SCHEDULED, FETCHING, VALIDATING, GENERATED, SENDING, SENT, FAILED
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    digest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    digest_type: Mapped[str] = mapped_column(String(40), default="production")  # production, test

