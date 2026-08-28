import pytest
from app.productivity.scoring import calculate_daily_totals, calculate_task_score
from app.productivity.models import TaskProgress


def test_video_scoring():
    # Video completed gives full 20 points
    assert calculate_task_score("video", 1.0, "done", 20.0, 1.0, "completed") == 20.0
    # Video pending or skipped gives 0
    assert calculate_task_score("video", 1.0, "done", 20.0, 0.0, "pending") == 0.0
    assert calculate_task_score("video", 1.0, "done", 20.0, 0.0, "skipped") == 0.0


def test_study_proportional_scoring_and_capping():
    # 3 / 4 * 50 = 37.5 points
    score = calculate_task_score("study", 4.0, "hours", 50.0, 3.0, "in_progress")
    assert score == 37.5

    # 4 / 4 * 50 = 50.0 points
    assert calculate_task_score("study", 4.0, "hours", 50.0, 4.0, "completed") == 50.0

    # Excessive hours (e.g. 8 hrs) must be strictly capped at 50 points
    assert calculate_task_score("study", 4.0, "hours", 50.0, 8.0, "completed") == 50.0


def test_exercise_proportional_scoring_and_capping():
    # 30 / 45 * 30 = 20.0 points
    score = calculate_task_score("exercise", 45.0, "minutes", 30.0, 30.0, "in_progress")
    assert score == 20.0

    # 45 / 45 * 30 = 30.0 points
    assert calculate_task_score("exercise", 45.0, "minutes", 30.0, 45.0, "completed") == 30.0

    # Excessive minutes (e.g. 90 min) capped at 30 points
    assert calculate_task_score("exercise", 45.0, "minutes", 30.0, 90.0, "completed") == 30.0


def test_daily_totals():
    tasks = [
        TaskProgress(1, "Video", "video", 1.0, "done", 20.0, "10:00", "completed", 1.0, 20.0),
        TaskProgress(2, "Study", "study", 4.0, "hours", 50.0, "14:00", "in_progress", 3.0, 37.5),
        TaskProgress(3, "Exercise", "exercise", 45.0, "minutes", 30.0, "18:00", "completed", 45.0, 30.0),
    ]
    total, max_score, pct = calculate_daily_totals(tasks)
    assert total == 87.5
    assert max_score == 100.0
    assert pct == 87.5
