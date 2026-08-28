from datetime import date, timedelta
from app.productivity.models import StreakStats


def compute_streak_stats(
    history: list,  # list of DailySummary or dict with date, score, completion_percentage
    threshold: float = 70.0,
    today_score: float | None = None,
    today_date: date | None = None,
) -> StreakStats:
    """Calculates current streak, longest streak, total successful days, missed days, and perfect days.
    
    A day qualifies if its score (or completion percentage) >= threshold.
    """
    if today_date is None:
        today_date = date.today()

    # Map dates to scores
    scores_by_date: dict[date, float] = {}
    for entry in history:
        # entry can have .date and .score (or .completion_percentage)
        d = getattr(entry, "date", None)
        s = getattr(entry, "score", None)
        if s is None:
            s = getattr(entry, "completion_percentage", 0.0)
        if d is not None and s is not None:
            scores_by_date[d] = float(s)

    if today_score is not None:
        scores_by_date[today_date] = today_score

    if not scores_by_date:
        return StreakStats(
            current_streak=0,
            longest_streak=0,
            total_successful_days=0,
            missed_days=0,
            perfect_days=0,
            threshold=threshold,
        )

    sorted_dates = sorted(scores_by_date.keys())
    
    total_successful_days = sum(1 for s in scores_by_date.values() if s >= threshold)
    missed_days = sum(1 for s in scores_by_date.values() if s < threshold)
    perfect_days = sum(1 for s in scores_by_date.values() if s >= 99.99)

    # Longest streak calculation
    longest_streak = 0
    current_running = 0
    prev_date = None

    for d in sorted_dates:
        s = scores_by_date[d]
        if s >= threshold:
            if prev_date is None or d == prev_date + timedelta(days=1):
                current_running += 1
            else:
                current_running = 1
            if current_running > longest_streak:
                longest_streak = current_running
        else:
            current_running = 0
        prev_date = d

    # Current streak calculation: count backwards from today or yesterday
    current_streak = 0
    check_date = today_date
    
    # If today meets threshold, start counting from today
    if scores_by_date.get(today_date, 0.0) >= threshold:
        check_date = today_date
    else:
        # If today doesn't meet threshold yet (day in progress), start checking from yesterday
        check_date = today_date - timedelta(days=1)

    while True:
        score = scores_by_date.get(check_date)
        if score is not None and score >= threshold:
            current_streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return StreakStats(
        current_streak=current_streak,
        longest_streak=longest_streak,
        total_successful_days=total_successful_days,
        missed_days=missed_days,
        perfect_days=perfect_days,
        threshold=threshold,
    )
