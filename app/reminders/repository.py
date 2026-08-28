from sqlalchemy import select
from sqlalchemy.orm import Session

from app.reminders.models import Reminder


class ReminderRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, user_id: int, text: str, trigger_at, recurrence: str | None = None) -> Reminder:
        reminder = Reminder(user_id=user_id, text=text, trigger_at=trigger_at, recurrence=recurrence)
        self.session.add(reminder)
        self.session.commit()
        return reminder

    def list(self, user_id: int) -> list[Reminder]:
        return list(self.session.scalars(select(Reminder).where(Reminder.user_id == user_id, Reminder.enabled.is_(True)).order_by(Reminder.trigger_at)))
