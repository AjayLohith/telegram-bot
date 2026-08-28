from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Task, User
from app.core.config import settings


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self.session.scalar(select(User).where(User.telegram_id == telegram_id))

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def list_active_users(self) -> list[User]:
        return list(self.session.scalars(select(User).where(User.is_paused == False)))

    def get_or_create(self, telegram_id: int, username: str | None = None) -> tuple[User, bool]:
        user = self.get_by_telegram_id(telegram_id)
        if user is not None:
            if username and user.username != username:
                user.username = username
                self.session.commit()
            return user, False

        user = User(
            telegram_id=telegram_id,
            username=username,
            timezone=settings.timezone,
            news_time=settings.news_time,
            morning_time=settings.morning_time,
            video_time=settings.video_reminder_time,
            study_time=settings.study_reminder_time,
            exercise_time=settings.exercise_reminder_time,
            eod_time=settings.eod_time,
            streak_threshold=settings.streak_threshold,
            breaking_news_enabled=settings.breaking_news_enabled,
            missed_reminders_enabled=settings.missed_reminders_enabled,
            morning_combined_enabled=settings.morning_combined_enabled,
        )
        self.session.add(user)
        self.session.flush()

        # Initialize default 3 predefined tasks
        default_tasks = [
            Task(
                user_id=user.id,
                name="A Video",
                task_type="video",
                target_value=1.0,
                target_unit="done",
                points=20.0,
                reminder_time=user.video_time,
                active=True,
            ),
            Task(
                user_id=user.id,
                name="Study Hours",
                task_type="study",
                target_value=4.0,
                target_unit="hours",
                points=50.0,
                reminder_time=user.study_time,
                active=True,
            ),
            Task(
                user_id=user.id,
                name="Exercise",
                task_type="exercise",
                target_value=45.0,
                target_unit="minutes",
                points=30.0,
                reminder_time=user.exercise_time,
                active=True,
            ),
        ]
        self.session.add_all(default_tasks)
        self.session.commit()
        return user, True

    def update_settings(self, telegram_id: int, **kwargs) -> User | None:
        user = self.get_by_telegram_id(telegram_id)
        if not user:
            return None
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        self.session.commit()
        return user
