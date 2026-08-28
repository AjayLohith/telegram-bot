from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.database.models import User, Task, TaskCompletion
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.user_repo import UserRepository
from app.productivity.service import ProductivityService


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as val:
        yield val


def test_user_creation_initializes_default_tasks(session):
    user_repo = UserRepository(session)
    user, is_new = user_repo.get_or_create(12345, "testuser")
    assert is_new is True
    assert user.telegram_id == 12345

    task_repo = TaskRepository(session)
    tasks = task_repo.get_user_tasks(user.id)
    assert len(tasks) == 3
    names = [t.name for t in tasks]
    assert "A Video" in names
    assert "Study Hours" in names
    assert "Exercise" in names


def test_complete_and_skip_tasks(session):
    user_repo = UserRepository(session)
    user, _ = user_repo.get_or_create(12345, "testuser")
    service = ProductivityService(session)
    today = date(2026, 8, 28)

    tasks = TaskRepository(session).get_user_tasks(user.id)
    video_task = next(t for t in tasks if t.task_type == "video")
    study_task = next(t for t in tasks if t.task_type == "study")
    exercise_task = next(t for t in tasks if t.task_type == "exercise")

    # Complete video
    service.complete_task(user.id, video_task.id, today, details={"video_title": "AI Architecture"})
    # Update study: 3 hours out of 4
    service.update_task_progress(user.id, study_task.id, today, actual_value=3.0, details={"subject": "Machine Learning"})
    # Skip exercise
    service.skip_task(user.id, exercise_task.id, today, remarks="Rest day")

    progress = service.get_daily_progress(user.id, today)
    assert progress.total_score == 20.0 + 37.5 + 0.0  # 57.5
    assert progress.max_score == 100.0
    assert progress.completion_percentage == 57.5

    v_prog = next(p for p in progress.tasks if p.task_id == video_task.id)
    assert v_prog.is_completed is True
    assert v_prog.details.get("video_title") == "AI Architecture"

    s_prog = next(p for p in progress.tasks if p.task_id == study_task.id)
    assert s_prog.actual_value == 3.0
    assert s_prog.score == 37.5

    e_prog = next(p for p in progress.tasks if p.task_id == exercise_task.id)
    assert e_prog.is_skipped is True
    assert e_prog.score == 0.0
