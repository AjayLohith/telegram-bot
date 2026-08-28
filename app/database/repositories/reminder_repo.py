from datetime import datetime, timezone as dt_timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Reminder


class ReminderRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_reminder(
        self,
        telegram_user_id: int,
        task_name: str,
        reminder_time_24h: str,
        display_time_12h: str,
        timezone: str = "Asia/Kolkata",
        recurrence: str = "DAILY",
    ) -> Reminder:
        reminder = Reminder(
            telegram_user_id=telegram_user_id,
            task_name=task_name,
            reminder_time=reminder_time_24h,
            display_time=display_time_12h,
            timezone=timezone,
            active=True,
            recurrence=recurrence,
            created_at=datetime.now(dt_timezone.utc),
        )
        self.session.add(reminder)
        self.session.commit()
        return reminder

    def get_reminder(self, reminder_id: int, telegram_user_id: int | None = None) -> Reminder | None:
        stmt = select(Reminder).where(Reminder.id == reminder_id)
        if telegram_user_id is not None:
            stmt = stmt.where(Reminder.telegram_user_id == telegram_user_id)
        return self.session.scalar(stmt)

    def list_user_reminders(self, telegram_user_id: int) -> list[Reminder]:
        stmt = (
            select(Reminder)
            .where(Reminder.telegram_user_id == telegram_user_id)
            .order_by(Reminder.reminder_time.asc())
        )
        return list(self.session.scalars(stmt))

    def list_active_reminders(self, telegram_user_id: int | None = None) -> list[Reminder]:
        stmt = select(Reminder).where(Reminder.active == True)
        if telegram_user_id is not None:
            stmt = stmt.where(Reminder.telegram_user_id == telegram_user_id)
        stmt = stmt.order_by(Reminder.reminder_time.asc())
        return list(self.session.scalars(stmt))

    def update_reminder(
        self,
        reminder_id: int,
        telegram_user_id: int,
        task_name: str | None = None,
        reminder_time: str | None = None,
        display_time: str | None = None,
    ) -> Reminder | None:
        reminder = self.get_reminder(reminder_id, telegram_user_id)
        if not reminder:
            return None
        if task_name is not None:
            reminder.task_name = task_name
        if reminder_time is not None:
            reminder.reminder_time = reminder_time
        if display_time is not None:
            reminder.display_time = display_time
        self.session.commit()
        return reminder

    def delete_reminder(self, reminder_id: int, telegram_user_id: int | None = None) -> bool:
        reminder = self.get_reminder(reminder_id, telegram_user_id)
        if not reminder:
            return False
        self.session.delete(reminder)
        self.session.commit()
        return True

    def set_active_status(self, reminder_id: int, telegram_user_id: int, active: bool) -> Reminder | None:
        reminder = self.get_reminder(reminder_id, telegram_user_id)
        if not reminder:
            return None
        reminder.active = active
        self.session.commit()
        return reminder

    def update_last_triggered(
        self,
        reminder_id: int,
        timestamp: datetime | None = None,
        ai_summary: str | None = None,
    ) -> None:
        reminder = self.session.get(Reminder, reminder_id)
        if reminder:
            reminder.last_triggered_at = timestamp or datetime.now(dt_timezone.utc)
            if ai_summary is not None:
                reminder.ai_summary = ai_summary
            self.session.commit()
