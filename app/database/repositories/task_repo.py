from datetime import date, datetime, timezone
import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Task, TaskCompletion


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_user_tasks(self, user_id: int, active_only: bool = True) -> list[Task]:
        stmt = select(Task).where(Task.user_id == user_id)
        if active_only:
            stmt = stmt.where(Task.active == True)
        stmt = stmt.order_by(Task.id.asc())
        return list(self.session.scalars(stmt))

    def get_task_by_id(self, task_id: int) -> Task | None:
        return self.session.get(Task, task_id)

    def add_task(
        self,
        user_id: int,
        name: str,
        task_type: str = "custom",
        target_value: float = 1.0,
        target_unit: str = "count",
        points: float = 20.0,
        reminder_time: str = "10:00",
    ) -> Task:
        task = Task(
            user_id=user_id,
            name=name,
            task_type=task_type,
            target_value=target_value,
            target_unit=target_unit,
            points=points,
            reminder_time=reminder_time,
            active=True,
        )
        self.session.add(task)
        self.session.commit()
        return task

    def update_task(self, task_id: int, **kwargs) -> Task | None:
        task = self.get_task_by_id(task_id)
        if not task:
            return None
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        self.session.commit()
        return task

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task_by_id(task_id)
        if not task:
            return False
        self.session.delete(task)
        self.session.commit()
        return True

    def get_completions_for_date(self, user_id: int, day: date) -> list[TaskCompletion]:
        stmt = select(TaskCompletion).where(
            TaskCompletion.user_id == user_id,
            TaskCompletion.date == day,
        )
        return list(self.session.scalars(stmt))

    def get_completion(self, user_id: int, task_id: int, day: date) -> TaskCompletion | None:
        stmt = select(TaskCompletion).where(
            TaskCompletion.user_id == user_id,
            TaskCompletion.task_id == task_id,
            TaskCompletion.date == day,
        )
        return self.session.scalar(stmt)

    def get_or_create_completion(self, user_id: int, task_id: int, day: date) -> TaskCompletion:
        comp = self.get_completion(user_id, task_id, day)
        if comp is not None:
            return comp
        comp = TaskCompletion(
            user_id=user_id,
            task_id=task_id,
            date=day,
            status="pending",
            actual_value=0.0,
            score=0.0,
        )
        self.session.add(comp)
        self.session.commit()
        return comp

    def record_completion(
        self,
        user_id: int,
        task_id: int,
        day: date,
        status: str,
        actual_value: float,
        score: float,
        details: dict | None = None,
        remarks: str | None = None,
    ) -> TaskCompletion:
        comp = self.get_or_create_completion(user_id, task_id, day)
        comp.status = status
        comp.actual_value = actual_value
        comp.score = score
        if details is not None:
            comp.details = json.dumps(details)
        if remarks is not None:
            comp.remarks = remarks
        comp.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        return comp
