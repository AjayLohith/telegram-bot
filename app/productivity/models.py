from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class TaskProgress:
    task_id: int
    name: str
    task_type: str
    target_value: float
    target_unit: str
    points: float
    reminder_time: str
    status: str  # pending, completed, skipped, in_progress
    actual_value: float
    score: float
    details: dict[str, Any] = field(default_factory=dict)
    remarks: str | None = None
    completed_at: datetime | None = None

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_skipped(self) -> bool:
        return self.status == "skipped"

    @property
    def completion_percentage(self) -> float:
        if self.target_value <= 0:
            return 100.0 if self.is_completed else 0.0
        return min(100.0, (self.actual_value / self.target_value) * 100.0)


@dataclass
class DailyProgress:
    user_id: int
    day: date
    tasks: list[TaskProgress]
    total_score: float
    max_score: float
    completion_percentage: float
    streak_days: int
    remarks: str | None = None


@dataclass
class StreakStats:
    current_streak: int
    longest_streak: int
    total_successful_days: int
    missed_days: int
    perfect_days: int
    threshold: float
