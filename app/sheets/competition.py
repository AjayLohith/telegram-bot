from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


DEFAULT_COMPETITION_DATA = {
    "settings": {
        "players": {
            "person_1": "Abhi",
            "person_2": "Ajay",
        },
        "daily_targets": {
            "wake_target": "05:00:00",
            "sleep_target": "23:30:00",
            "study_target_hrs": 8.0,
            "english_practice_target_hrs": 1.0,
            "step_target": 10000,
        },
        "scoring_weights_total_100": {
            "wake_time_points": 10,
            "sleep_time_points": 10,
            "study_points": 25,
            "english_practice_points": 15,
            "workout_points": 15,
            "steps_points": 15,
            "no_junk_food_points": 10,
        },
        "streaks_config": {
            "successful_day_threshold_pct": 70,
        },
    },
    "competition_standings": {
        "today_winner": "Abhi",
        "current_leader": "Abhi",
        "score_difference": 33.2,
        "standings": {
            "Abhi": {
                "total_points": 56.3,
                "average_score": 28.2,
                "wins": 1,
                "losses": 0,
                "draws": 0,
            },
            "Ajay": {
                "total_points": 23.1,
                "average_score": 23.1,
                "wins": 0,
                "losses": 1,
                "draws": 0,
            },
        },
    },
    "streaks": [
        {
            "metric": "Current Overall Streak",
            "Abhi": 0,
            "Ajay": 0,
            "definition": "Consecutive tracked days scoring ≥ threshold (70%)",
        },
        {
            "metric": "Longest Overall Streak",
            "Abhi": 0,
            "Ajay": 0,
            "definition": "Best-ever run of successful days",
        },
        {
            "metric": "Wake Target Streak",
            "Abhi": 0,
            "Ajay": 0,
            "definition": "Consecutive days waking within 30 min of target",
        },
        {
            "metric": "Sleep Target Streak",
            "Abhi": 1,
            "Ajay": 1,
            "definition": "Consecutive days sleeping within 30 min of target",
        },
        {
            "metric": "Study Streak",
            "Abhi": 0,
            "Ajay": 0,
            "definition": "Consecutive days meeting the study hour target",
        },
        {
            "metric": "English Practice Streak",
            "Abhi": 0,
            "Ajay": 0,
            "definition": "Consecutive days meeting the English practice target",
        },
        {
            "metric": "Workout Streak",
            "Abhi": 1,
            "Ajay": 0,
            "definition": "Consecutive days with workout checked",
        },
        {
            "metric": "Step Target Streak",
            "Abhi": 1,
            "Ajay": 0,
            "definition": "Consecutive days meeting the step target",
        },
        {
            "metric": "No Junk Food Streak",
            "Abhi": 1,
            "Ajay": 1,
            "definition": "Consecutive days without junk food",
        },
    ],
    "daily_tracker": [
        {
            "date": "2026-08-28",
            "Abhi": {
                "wake_time": None,
                "sleep_time": None,
                "study_hrs": 0,
                "english_hrs": 0,
                "workout": False,
                "steps": None,
                "junk_food": None,
                "remarks": None,
                "score": 0,
                "completion_pct": "0%",
            },
            "Ajay": {
                "wake_time": None,
                "sleep_time": None,
                "study_hrs": None,
                "english_hrs": None,
                "workout": None,
                "steps": None,
                "junk_food": None,
                "remarks": None,
                "score": None,
                "completion_pct": None,
            },
            "result": {
                "winner": None,
                "point_diff": None,
            },
        },
        {
            "date": "2026-08-29",
            "Abhi": {
                "wake_time": "08:00:00",
                "sleep_time": "23:30:00",
                "study_hrs": 2.0,
                "english_hrs": 0.0,
                "workout": True,
                "steps": 12385,
                "junk_food": False,
                "remarks": "Basic Workouts done and No English",
                "score": 56.3,
                "completion_pct": "56%",
            },
            "Ajay": {
                "wake_time": "07:00:00",
                "sleep_time": "23:30:00",
                "study_hrs": 1.0,
                "english_hrs": 0.0,
                "workout": False,
                "steps": 0,
                "junk_food": False,
                "remarks": "Repu day1",
                "score": 23.1,
                "completion_pct": "23%",
            },
            "result": {
                "winner": "Abhi",
                "point_diff": 33.2,
            },
        },
    ],
}


class CompetitionTrackerEngine:
    """Specialized engine for 2-Person Daily Competition Tracker."""

    @staticmethod
    def parse_competition_grid(raw_values: list[list[str]], existing_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Dynamically parses raw 2D grid from Google Sheet into structured competition data."""
        data = dict(existing_data or DEFAULT_COMPETITION_DATA)
        if not raw_values or len(raw_values) < 2:
            return data

        logged_days = []
        p1_name = data.get("settings", {}).get("players", {}).get("person_1", "Abhi")
        p2_name = data.get("settings", {}).get("players", {}).get("person_2", "Ajay")

        # Scan for tracker rows
        for row in raw_values:
            if not row or not row[0].strip():
                continue
            first_cell = row[0].strip()
            # Check if first cell looks like a date (e.g. 2026-..., 28/..., 29-...)
            if not any(sep in first_cell for sep in ("-", "/")) and not first_cell.startswith("20"):
                continue

            # Standard 23-column tracker format
            if len(row) >= 10:
                def safe_float(val: Any, default: float = 0.0) -> float:
                    if not val:
                        return default
                    try:
                        clean = str(val).replace("%", "").replace("₹", "").replace("$", "").replace(",", "").strip()
                        return float(clean)
                    except ValueError:
                        return default

                def safe_int(val: Any, default: int = 0) -> int:
                    if not val:
                        return default
                    try:
                        clean = str(val).replace(",", "").strip()
                        return int(float(clean))
                    except ValueError:
                        return default

                def safe_bool(val: Any) -> bool:
                    return str(val).strip().lower() in ("true", "yes", "y", "1")

                p1_entry = {
                    "wake_time": row[1].strip() if len(row) > 1 and row[1].strip() else None,
                    "sleep_time": row[2].strip() if len(row) > 2 and row[2].strip() else None,
                    "study_hrs": safe_float(row[3] if len(row) > 3 else 0),
                    "english_hrs": safe_float(row[4] if len(row) > 4 else 0),
                    "workout": safe_bool(row[5] if len(row) > 5 else False),
                    "steps": safe_int(row[6] if len(row) > 6 else 0),
                    "junk_food": safe_bool(row[7] if len(row) > 7 else False),
                    "remarks": row[8].strip() if len(row) > 8 and row[8].strip() else None,
                    "score": safe_float(row[9] if len(row) > 9 else 0),
                    "completion_pct": f"{int(safe_float(row[10] if len(row) > 10 else row[9] if len(row) > 9 else 0))}%",
                }

                p2_entry = {
                    "wake_time": row[11].strip() if len(row) > 11 and row[11].strip() else None,
                    "sleep_time": row[12].strip() if len(row) > 12 and row[12].strip() else None,
                    "study_hrs": safe_float(row[13] if len(row) > 13 else 0),
                    "english_hrs": safe_float(row[14] if len(row) > 14 else 0),
                    "workout": safe_bool(row[15] if len(row) > 15 else False),
                    "steps": safe_int(row[16] if len(row) > 16 else 0),
                    "junk_food": safe_bool(row[17] if len(row) > 17 else False),
                    "remarks": row[18].strip() if len(row) > 18 and row[18].strip() else None,
                    "score": safe_float(row[19] if len(row) > 19 else 0),
                    "completion_pct": f"{int(safe_float(row[20] if len(row) > 20 else row[19] if len(row) > 19 else 0))}%",
                }

                # Determine winner from scores or result column
                winner = row[21].strip() if len(row) > 21 and row[21].strip() else None
                diff = safe_float(row[22] if len(row) > 22 else 0)

                if not winner:
                    if p1_entry["score"] > p2_entry["score"]:
                        winner = p1_name
                        diff = round(p1_entry["score"] - p2_entry["score"], 1)
                    elif p2_entry["score"] > p1_entry["score"]:
                        winner = p2_name
                        diff = round(p2_entry["score"] - p1_entry["score"], 1)
                    elif p1_entry["score"] > 0:
                        winner = "Draw"
                        diff = 0.0

                logged_days.append({
                    "date": first_cell,
                    p1_name: p1_entry,
                    p2_name: p2_entry,
                    "result": {
                        "winner": winner,
                        "point_diff": diff,
                    },
                })

        if logged_days:
            data["daily_tracker"] = logged_days

            # Recalculate standings
            p1_total = sum(d.get(p1_name, {}).get("score", 0) for d in logged_days)
            p2_total = sum(d.get(p2_name, {}).get("score", 0) for d in logged_days)
            p1_wins = sum(1 for d in logged_days if d.get("result", {}).get("winner") == p1_name)
            p2_wins = sum(1 for d in logged_days if d.get("result", {}).get("winner") == p2_name)
            draws = sum(1 for d in logged_days if d.get("result", {}).get("winner") == "Draw")

            latest_winner = logged_days[-1].get("result", {}).get("winner") or (p1_name if p1_total >= p2_total else p2_name)
            current_leader = p1_name if p1_total >= p2_total else p2_name
            score_diff = round(abs(p1_total - p2_total), 1)

            data["competition_standings"] = {
                "today_winner": latest_winner,
                "current_leader": current_leader,
                "score_difference": score_diff,
                "standings": {
                    p1_name: {
                        "total_points": round(p1_total, 1),
                        "average_score": round(p1_total / len(logged_days), 1) if logged_days else 0,
                        "wins": p1_wins,
                        "losses": p2_wins,
                        "draws": draws,
                    },
                    p2_name: {
                        "total_points": round(p2_total, 1),
                        "average_score": round(p2_total / len(logged_days), 1) if logged_days else 0,
                        "wins": p2_wins,
                        "losses": p1_wins,
                        "draws": draws,
                    },
                },
            }

        return data

    @staticmethod
    def format_winner_today(data: dict[str, Any] = DEFAULT_COMPETITION_DATA) -> str:
        standings = data.get("competition_standings", {})
        daily = data.get("daily_tracker", [])
        
        # Get latest day with result
        latest_entry = None
        for day in reversed(daily):
            if day.get("result", {}).get("winner"):
                latest_entry = day
                break
        
        if not latest_entry:
            winner = standings.get("today_winner", "Abhi")
            diff = standings.get("score_difference", 33.2)
            latest_date = "Today"
            p1_score = 56.3
            p2_score = 23.1
        else:
            winner = latest_entry["result"]["winner"] or "Abhi"
            diff = latest_entry["result"]["point_diff"] or 0.0
            latest_date = latest_entry.get("date", "Today")
            p1_score = latest_entry.get("Abhi", {}).get("score", 0)
            p2_score = latest_entry.get("Ajay", {}).get("score", 0)

        p1_pct = latest_entry.get("Abhi", {}).get("completion_pct", "56%") if latest_entry else "56%"
        p2_pct = latest_entry.get("Ajay", {}).get("completion_pct", "23%") if latest_entry else "23%"

        congrats_line = (
            f"<i>🔥 Great hustle by {winner}! Keep pushing, {'Ajay' if winner == 'Abhi' else 'Abhi'}! 💪</i>"
        )

        return (
            f"🏆 <b>TODAY'S WINNER: {winner.upper()}</b>\n\n"
            f"📅 <b>Date:</b> {latest_date}\n"
            f"🥇 <b>{winner}</b> won by a margin of <b>+{diff:.1f} pts</b>!\n\n"
            f"<b>📊 Scores Breakdown:</b>\n"
            f"• 👤 <b>Abhi:</b> {p1_score} pts ({p1_pct})\n"
            f"• 👤 <b>Ajay:</b> {p2_score} pts ({p2_pct})\n\n"
            f"{congrats_line}"
        )

    @staticmethod
    def format_leaderboard(data: dict[str, Any] = DEFAULT_COMPETITION_DATA) -> str:
        standings_obj = data.get("competition_standings", {})
        leader = standings_obj.get("current_leader", "Abhi")
        diff = standings_obj.get("score_difference", 33.2)
        standings = standings_obj.get("standings", {})

        lines = [
            "📊 <b>DAILY COMPETITION LEADERBOARD</b>\n",
            f"👑 <b>Current Leader:</b> <b>{leader}</b> (+{diff:.1f} pts)\n",
        ]

        for player, stats in standings.items():
            rank_icon = "🥇" if player == leader else "🥈"
            lines.append(
                f"{rank_icon} <b>{player}</b>\n"
                f"  • <b>Total Points:</b> {stats.get('total_points', 0)} pts\n"
                f"  • <b>Average Score:</b> {stats.get('average_score', 0)} pts\n"
                f"  • <b>Win Record:</b> {stats.get('wins', 0)}W - {stats.get('losses', 0)}L - {stats.get('draws', 0)}D\n"
            )

        return "\n".join(lines)

    @staticmethod
    def format_streaks(data: dict[str, Any] = DEFAULT_COMPETITION_DATA) -> str:
        streaks = data.get("streaks", [])
        lines = [
            "🔥 <b>HABIT & METRIC STREAKS</b>\n",
        ]

        for s in streaks:
            metric = s.get("metric")
            abhi_streak = s.get("Abhi", 0)
            ajay_streak = s.get("Ajay", 0)
            lines.append(f"• <b>{metric}:</b> Abhi: <code>{abhi_streak}d</code> | Ajay: <code>{ajay_streak}d</code>")

        lines.append("\n🎯 <i>Qualifying threshold: ≥70% daily score</i>")
        return "\n".join(lines)

    @staticmethod
    def format_daily_log(data: dict[str, Any] = DEFAULT_COMPETITION_DATA, date_str: str | None = None) -> str:
        daily = data.get("daily_tracker", [])
        
        entry = None
        if date_str:
            for day in daily:
                if day.get("date") == date_str:
                    entry = day
                    break
        if not entry and daily:
            entry = daily[-1]

        if not entry:
            return "No logged tracker entries available."

        d_val = entry.get("date", "Recent")
        abhi = entry.get("Abhi", {})
        ajay = entry.get("Ajay", {})
        res = entry.get("result", {})

        return (
            f"📅 <b>DAILY TRACKER LOG — {d_val}</b>\n\n"
            f"👤 <b>ABHI ({abhi.get('score', 0)} pts - {abhi.get('completion_pct', '0%')}):</b>\n"
            f"• ⏰ Wake: {abhi.get('wake_time') or 'N/A'} | Sleep: {abhi.get('sleep_time') or 'N/A'}\n"
            f"• 📚 Study: {abhi.get('study_hrs', 0)}h | 🗣 English: {abhi.get('english_hrs', 0)}h\n"
            f"• 🏃 Workout: {'✅' if abhi.get('workout') else '❌'} | 👣 Steps: {abhi.get('steps') or 0:,}\n"
            f"• 🍔 No Junk Food: {'✅' if not abhi.get('junk_food') else '❌'}\n"
            f"• 📝 Remarks: <i>{abhi.get('remarks') or 'None'}</i>\n\n"
            f"👤 <b>AJAY ({ajay.get('score', 0)} pts - {ajay.get('completion_pct', '0%')}):</b>\n"
            f"• ⏰ Wake: {ajay.get('wake_time') or 'N/A'} | Sleep: {ajay.get('sleep_time') or 'N/A'}\n"
            f"• 📚 Study: {ajay.get('study_hrs', 0)}h | 🗣 English: {ajay.get('english_hrs', 0)}h\n"
            f"• 🏃 Workout: {'✅' if ajay.get('workout') else '❌'} | 👣 Steps: {ajay.get('steps') or 0:,}\n"
            f"• 🍔 No Junk Food: {'✅' if not ajay.get('junk_food') else '❌'}\n"
            f"• 📝 Remarks: <i>{ajay.get('remarks') or 'None'}</i>\n\n"
            f"🏆 <b>Result:</b> {res.get('winner', 'Draw')} (+{res.get('point_diff', 0)} pts)"
        )
