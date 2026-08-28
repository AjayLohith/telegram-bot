from datetime import date
from sqlalchemy.orm import Session

from app.database.repositories.user_repo import UserRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.summary_repo import SummaryRepository
from app.productivity.models import DailyProgress, TaskProgress, StreakStats
from app.productivity.scoring import calculate_task_score, calculate_daily_totals
from app.productivity.streak import compute_streak_stats


class ProductivityService:
    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)
        self.task_repo = TaskRepository(session)
        self.summary_repo = SummaryRepository(session)

    def get_daily_progress(self, user_id: int, day: date) -> DailyProgress:
        user = self.user_repo.get_by_id(user_id)
        threshold = user.streak_threshold if user else 70.0

        tasks = self.task_repo.get_user_tasks(user_id, active_only=True)
        completions = self.task_repo.get_completions_for_date(user_id, day)
        comp_map = {c.task_id: c for c in completions}

        tasks_progress: list[TaskProgress] = []
        for task in tasks:
            comp = comp_map.get(task.id)
            if comp:
                status = comp.status
                actual_value = comp.actual_value
                score = comp.score
                details = comp.get_details_dict()
                remarks = comp.remarks
                completed_at = comp.completed_at
            else:
                status = "pending"
                actual_value = 0.0
                score = 0.0
                details = {}
                remarks = None
                completed_at = None

            tasks_progress.append(
                TaskProgress(
                    task_id=task.id,
                    name=task.name,
                    task_type=task.task_type,
                    target_value=task.target_value,
                    target_unit=task.target_unit,
                    points=task.points,
                    reminder_time=task.reminder_time,
                    status=status,
                    actual_value=actual_value,
                    score=score,
                    details=details,
                    remarks=remarks,
                    completed_at=completed_at,
                )
            )

        total_score, max_score, completion_pct = calculate_daily_totals(tasks_progress)
        history = self.summary_repo.get_all_summaries(user_id)
        streak_stats = compute_streak_stats(history, threshold=threshold, today_score=total_score, today_date=day)

        summary_entry = self.summary_repo.get_daily_summary(user_id, day)
        day_remarks = summary_entry.remarks if summary_entry else None

        return DailyProgress(
            user_id=user_id,
            day=day,
            tasks=tasks_progress,
            total_score=total_score,
            max_score=max_score,
            completion_percentage=completion_pct,
            streak_days=streak_stats.current_streak,
            remarks=day_remarks,
        )

    def complete_task(
        self,
        user_id: int,
        task_id: int,
        day: date,
        actual_value: float | None = None,
        details: dict | None = None,
        remarks: str | None = None,
    ) -> TaskProgress:
        task = self.task_repo.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        val = actual_value if actual_value is not None else task.target_value
        score = calculate_task_score(
            task_type=task.task_type,
            target_value=task.target_value,
            target_unit=task.target_unit,
            max_points=task.points,
            actual_value=val,
            status="completed",
        )

        comp = self.task_repo.record_completion(
            user_id=user_id,
            task_id=task_id,
            day=day,
            status="completed",
            actual_value=val,
            score=score,
            details=details,
            remarks=remarks,
        )

        return TaskProgress(
            task_id=task.id,
            name=task.name,
            task_type=task.task_type,
            target_value=task.target_value,
            target_unit=task.target_unit,
            points=task.points,
            reminder_time=task.reminder_time,
            status="completed",
            actual_value=comp.actual_value,
            score=comp.score,
            details=comp.get_details_dict(),
            remarks=comp.remarks,
            completed_at=comp.completed_at,
        )

    def skip_task(
        self,
        user_id: int,
        task_id: int,
        day: date,
        remarks: str | None = None,
    ) -> TaskProgress:
        task = self.task_repo.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        comp = self.task_repo.record_completion(
            user_id=user_id,
            task_id=task_id,
            day=day,
            status="skipped",
            actual_value=0.0,
            score=0.0,
            remarks=remarks,
        )

        return TaskProgress(
            task_id=task.id,
            name=task.name,
            task_type=task.task_type,
            target_value=task.target_value,
            target_unit=task.target_unit,
            points=task.points,
            reminder_time=task.reminder_time,
            status="skipped",
            actual_value=0.0,
            score=0.0,
            details={},
            remarks=comp.remarks,
            completed_at=comp.completed_at,
        )

    def update_task_progress(
        self,
        user_id: int,
        task_id: int,
        day: date,
        actual_value: float,
        details: dict | None = None,
        remarks: str | None = None,
    ) -> TaskProgress:
        task = self.task_repo.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        status = "completed" if actual_value >= task.target_value else "in_progress"
        score = calculate_task_score(
            task_type=task.task_type,
            target_value=task.target_value,
            target_unit=task.target_unit,
            max_points=task.points,
            actual_value=actual_value,
            status=status,
        )

        comp = self.task_repo.record_completion(
            user_id=user_id,
            task_id=task_id,
            day=day,
            status=status,
            actual_value=actual_value,
            score=score,
            details=details,
            remarks=remarks,
        )

        return TaskProgress(
            task_id=task.id,
            name=task.name,
            task_type=task.task_type,
            target_value=task.target_value,
            target_unit=task.target_unit,
            points=task.points,
            reminder_time=task.reminder_time,
            status=status,
            actual_value=comp.actual_value,
            score=comp.score,
            details=comp.get_details_dict(),
            remarks=comp.remarks,
            completed_at=comp.completed_at,
        )

    def save_eod_summary(self, user_id: int, day: date, remarks: str | None = None) -> DailyProgress:
        progress = self.get_daily_progress(user_id, day)
        self.summary_repo.save_daily_summary(
            user_id=user_id,
            day=day,
            score=progress.total_score,
            completion_pct=progress.completion_percentage,
            remarks=remarks or progress.remarks,
            streak_days=progress.streak_days,
        )
        return progress

    def get_missed_tasks(self, user_id: int, day: date) -> list[TaskProgress]:
        progress = self.get_daily_progress(user_id, day)
        return [t for t in progress.tasks if t.status not in {"completed", "skipped"} and t.actual_value < t.target_value]

    def get_streak_stats(self, user_id: int, day: date | None = None) -> StreakStats:
        if day is None:
            day = date.today()
        user = self.user_repo.get_by_id(user_id)
        threshold = user.streak_threshold if user else 70.0
        history = self.summary_repo.get_all_summaries(user_id)
        current_progress = self.get_daily_progress(user_id, day)
        return compute_streak_stats(
            history,
            threshold=threshold,
            today_score=current_progress.total_score,
            today_date=day,
        )
