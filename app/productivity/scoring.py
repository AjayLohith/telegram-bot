def calculate_task_score(
    task_type: str,
    target_value: float,
    target_unit: str,
    max_points: float,
    actual_value: float,
    status: str,
) -> float:
    """Calculate the score for a task based on completion and target values.
    
    Capped strictly at max_points. No excessive hours/duration can generate unlimited points.
    """
    if status == "skipped":
        return 0.0

    if task_type == "video":
        # Video is binary completion (or 0 if not completed)
        return max_points if status == "completed" or actual_value >= 1.0 else 0.0

    if task_type in {"study", "exercise"} or target_unit in {"hours", "minutes", "count"}:
        if target_value <= 0:
            return max_points if (status == "completed" or actual_value > 0) else 0.0
        # Proportional score
        ratio = actual_value / target_value
        calculated = ratio * max_points
        return round(min(max_points, max(0.0, calculated)), 2)

    # General custom tasks: full points if marked completed, otherwise proportional if actual_value given
    if status == "completed":
        return max_points
    if target_value > 0 and actual_value > 0:
        return round(min(max_points, max(0.0, (actual_value / target_value) * max_points)), 2)
    return 0.0


def calculate_daily_totals(tasks_progress: list) -> tuple[float, float, float]:
    """Returns (total_score, max_possible_score, completion_percentage)"""
    total_score = sum(t.score for t in tasks_progress)
    max_score = sum(t.points for t in tasks_progress)
    completion_pct = round((total_score / max_score) * 100.0, 2) if max_score > 0 else 0.0
    return round(total_score, 2), round(max_score, 2), completion_pct
