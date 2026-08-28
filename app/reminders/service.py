from dataclasses import dataclass
from datetime import datetime, timedelta
import re


@dataclass(frozen=True)
class ReminderDraft:
    text: str
    trigger_at: datetime
    recurrence: str | None = None


_DURATION = re.compile(r"remind me in (?P<amount>\d+) (?P<unit>minute|minutes|hour|hours|day|days)", re.I)


def parse_relative_reminder(message: str, now: datetime) -> ReminderDraft | None:
    match = _DURATION.search(message)
    if not match:
        return None
    amount = int(match.group("amount"))
    unit = match.group("unit").lower()
    delta = {"minute": timedelta(minutes=amount), "minutes": timedelta(minutes=amount), "hour": timedelta(hours=amount), "hours": timedelta(hours=amount), "day": timedelta(days=amount), "days": timedelta(days=amount)}[unit]
    text = re.sub(r"^\s*/?remind me in .*?\s+to\s+", "", message, flags=re.I).strip() or message.strip()
    return ReminderDraft(text=text, trigger_at=now + delta)
