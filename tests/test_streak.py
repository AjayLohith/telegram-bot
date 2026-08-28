from datetime import date, timedelta
from app.productivity.streak import compute_streak_stats


class MockSummary:
    def __init__(self, d: date, s: float):
        self.date = d
        self.score = s


def test_streak_calculation_consecutive_days():
    base = date(2026, 8, 20)
    # 5 consecutive qualifying days (score >= 70)
    history = [
        MockSummary(base + timedelta(days=0), 80.0),
        MockSummary(base + timedelta(days=1), 75.0),
        MockSummary(base + timedelta(days=2), 100.0),
        MockSummary(base + timedelta(days=3), 90.0),
        MockSummary(base + timedelta(days=4), 85.0),
    ]

    stats = compute_streak_stats(history, threshold=70.0, today_date=base + timedelta(days=4))
    assert stats.current_streak == 5
    assert stats.longest_streak == 5
    assert stats.total_successful_days == 5
    assert stats.perfect_days == 1
    assert stats.missed_days == 0


def test_streak_resets_on_missed_day():
    base = date(2026, 8, 20)
    history = [
        MockSummary(base + timedelta(days=0), 80.0),
        MockSummary(base + timedelta(days=1), 90.0),
        MockSummary(base + timedelta(days=2), 50.0),  # Missed day! (< 70)
        MockSummary(base + timedelta(days=3), 85.0),
        MockSummary(base + timedelta(days=4), 95.0),
    ]

    stats = compute_streak_stats(history, threshold=70.0, today_date=base + timedelta(days=4))
    assert stats.current_streak == 2
    assert stats.longest_streak == 2
    assert stats.total_successful_days == 4
    assert stats.missed_days == 1


def test_streak_in_progress_today_does_not_break_prior_streak():
    base = date(2026, 8, 20)
    # Yesterday had 80.0, today has 20.0 (day in progress)
    history = [
        MockSummary(base, 80.0),
        MockSummary(base + timedelta(days=1), 85.0),
    ]
    today = base + timedelta(days=2)
    stats = compute_streak_stats(history, threshold=70.0, today_score=20.0, today_date=today)
    # Current streak should still recognize 2 consecutive completed days
    assert stats.current_streak == 2
