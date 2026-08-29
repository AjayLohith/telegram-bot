from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings


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
    def clean_date_str(date_val: Any) -> str:
        """Cleans ISO timestamp strings like 2026-08-29T08:00:00.000Z to 2026-08-29."""
        if not date_val:
            return "Today"
        s = str(date_val).strip()
        if "T" in s:
            s = s.split("T")[0]
        elif " " in s:
            s = s.split(" ")[0]
        return s

    @staticmethod
    def clean_time_str(time_val: Any, tz_str: str = "Asia/Kolkata") -> str:
        """Cleans timestamps to standard 24-hour format HH:MM (e.g. 08:00, 23:30), converting UTC ISO if present."""
        if not time_val:
            return "N/A"
        s = str(time_val).strip()
        if not s or s.lower() in ("none", "null", "n/a", "pending"):
            return "N/A"
        
        # If it's an ISO timestamp with Date part (e.g. 1899-12-30T02:30:00.000Z)
        if "T" in s or "t" in s:
            try:
                # If ends with Z, parse as UTC and convert to target timezone (IST)
                if s.endswith("Z") or s.endswith("z"):
                    dt_utc = datetime.fromisoformat(s.replace("Z", "+00:00").replace("z", "+00:00"))
                    dt_local = dt_utc.astimezone(ZoneInfo(tz_str))
                    return dt_local.strftime("%H:%M")
                else:
                    time_part = s.split("T" if "T" in s else "t")[1].split(".")[0].strip()
                    parts = time_part.split(":")
                    if len(parts) >= 2:
                        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
            except Exception:
                pass

        # Check for 12-hour AM/PM string (e.g. "4:00 PM", "07:30 AM")
        s_upper = s.upper()
        if "AM" in s_upper or "PM" in s_upper:
            is_pm = "PM" in s_upper
            clean_s = s_upper.replace("AM", "").replace("PM", "").strip()
            parts = clean_s.split(":")
            if len(parts) >= 2:
                try:
                    hr = int(parts[0])
                    mn = int(parts[1])
                    if is_pm and hr < 12:
                        hr += 12
                    elif not is_pm and hr == 12:
                        hr = 0
                    return f"{hr:02d}:{mn:02d}"
                except ValueError:
                    pass

        parts = s.split(":")
        if len(parts) >= 2:
            try:
                hr = int(parts[0])
                mn = int(parts[1])
                return f"{hr:02d}:{mn:02d}"
            except ValueError:
                pass
        return s

    @staticmethod
    def parse_competition_grid(raw_values: list[list[str]], existing_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Dynamically parses raw 2D grid from Google Sheet into structured competition data, filtering out empty template rows."""
        data = dict(existing_data or DEFAULT_COMPETITION_DATA)
        if not raw_values or len(raw_values) < 2:
            return data

        logged_days = []
        p1_name = data.get("settings", {}).get("players", {}).get("person_1", "Abhi")
        p2_name = data.get("settings", {}).get("players", {}).get("person_2", "Ajay")
        tz_str = settings.timezone or "Asia/Kolkata"

        # Scan for tracker rows
        for row in raw_values:
            if not row or not row[0].strip():
                continue
            first_cell = CompetitionTrackerEngine.clean_date_str(row[0])
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
                        return round(float(clean), 2)
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

                p1_wake = CompetitionTrackerEngine.clean_time_str(row[1] if len(row) > 1 else None, tz_str)
                p1_sleep = CompetitionTrackerEngine.clean_time_str(row[2] if len(row) > 2 else None, tz_str)
                p1_study = safe_float(row[3] if len(row) > 3 else 0)
                p1_english = safe_float(row[4] if len(row) > 4 else 0)
                p1_workout = safe_bool(row[5] if len(row) > 5 else False)
                p1_steps = safe_int(row[6] if len(row) > 6 else 0)
                p1_junk = safe_bool(row[7] if len(row) > 7 else False)
                p1_remarks = row[8].strip() if len(row) > 8 and row[8].strip() else None
                p1_score = safe_float(row[9] if len(row) > 9 else 0)
                
                # Format completion percentage
                raw_p1_pct = safe_float(row[10] if len(row) > 10 else 0)
                if 0 < raw_p1_pct <= 1.0:
                    raw_p1_pct = round(raw_p1_pct * 100, 1)
                p1_pct = f"{raw_p1_pct:.1f}%" if raw_p1_pct > 0 else (f"{p1_score:.1f}%" if p1_score > 0 else "0%")

                p2_wake = CompetitionTrackerEngine.clean_time_str(row[11] if len(row) > 11 else None, tz_str)
                p2_sleep = CompetitionTrackerEngine.clean_time_str(row[12] if len(row) > 12 else None, tz_str)
                p2_study = safe_float(row[13] if len(row) > 13 else 0)
                p2_english = safe_float(row[14] if len(row) > 14 else 0)
                p2_workout = safe_bool(row[15] if len(row) > 15 else False)
                p2_steps = safe_int(row[16] if len(row) > 16 else 0)
                p2_junk = safe_bool(row[17] if len(row) > 17 else False)
                p2_remarks = row[18].strip() if len(row) > 18 and row[18].strip() else None
                p2_score = safe_float(row[19] if len(row) > 19 else 0)
                
                raw_p2_pct = safe_float(row[20] if len(row) > 20 else 0)
                if 0 < raw_p2_pct <= 1.0:
                    raw_p2_pct = round(raw_p2_pct * 100, 1)
                p2_pct = f"{raw_p2_pct:.1f}%" if raw_p2_pct > 0 else (f"{p2_score:.1f}%" if p2_score > 0 else "0%")

                # Check if this row is an empty future template row
                has_p1_data = bool(p1_wake != "N/A" or p1_sleep != "N/A" or p1_study > 0 or p1_english > 0 or p1_workout or p1_steps > 0 or p1_remarks or p1_score > 0)
                has_p2_data = bool(p2_wake != "N/A" or p2_sleep != "N/A" or p2_study > 0 or p2_english > 0 or p2_workout or p2_steps > 0 or p2_remarks or p2_score > 0)

                # Skip completely blank/future template rows
                if not has_p1_data and not has_p2_data:
                    continue

                p1_entry = {
                    "wake_time": p1_wake,
                    "sleep_time": p1_sleep,
                    "study_hrs": p1_study,
                    "english_hrs": p1_english,
                    "workout": p1_workout,
                    "steps": p1_steps,
                    "junk_food": p1_junk,
                    "remarks": p1_remarks,
                    "score": p1_score,
                    "completion_pct": p1_pct,
                }

                p2_entry = {
                    "wake_time": p2_wake,
                    "sleep_time": p2_sleep,
                    "study_hrs": p2_study,
                    "english_hrs": p2_english,
                    "workout": p2_workout,
                    "steps": p2_steps,
                    "junk_food": p2_junk,
                    "remarks": p2_remarks,
                    "score": p2_score,
                    "completion_pct": p2_pct,
                }

                # Determine winner from scores or result column
                winner = row[21].strip() if len(row) > 21 and row[21].strip() else None
                diff = safe_float(row[22] if len(row) > 22 else 0)

                if not winner or winner.lower() in ("none", "null", ""):
                    if p1_score > p2_score:
                        winner = p1_name
                        diff = round(p1_score - p2_score, 2)
                    elif p2_score > p1_score:
                        winner = p2_name
                        diff = round(p2_score - p1_score, 2)
                    elif p1_score > 0:
                        winner = "Draw"
                        diff = 0.0
                    else:
                        winner = None
                        diff = 0.0
                else:
                    diff = round(abs(p1_score - p2_score), 2) if diff == 0 and p1_score != p2_score else round(diff, 2)

                logged_days.append({
                    "date": first_cell,
                    p1_name: p1_entry,
                    p2_name: p2_entry,
                    "result": {
                        "winner": winner,
                        "point_diff": round(diff, 2),
                    },
                })

        if logged_days:
            data["daily_tracker"] = logged_days

            # Recalculate standings from logged days
            p1_total = sum(d.get(p1_name, {}).get("score", 0) for d in logged_days)
            p2_total = sum(d.get(p2_name, {}).get("score", 0) for d in logged_days)
            p1_wins = sum(1 for d in logged_days if d.get("result", {}).get("winner") == p1_name)
            p2_wins = sum(1 for d in logged_days if d.get("result", {}).get("winner") == p2_name)
            draws = sum(1 for d in logged_days if d.get("result", {}).get("winner") == "Draw")

            # Get the latest day that actually had a winner/score
            latest_day_with_result = next((d for d in reversed(logged_days) if d.get("result", {}).get("winner")), logged_days[-1])
            latest_winner = latest_day_with_result.get("result", {}).get("winner") or (p1_name if p1_total >= p2_total else p2_name)
            current_leader = p1_name if p1_total >= p2_total else p2_name
            score_diff = round(abs(p1_total - p2_total), 2)

            data["competition_standings"] = {
                "today_winner": latest_winner,
                "current_leader": current_leader,
                "score_difference": score_diff,
                "standings": {
                    p1_name: {
                        "total_points": round(p1_total, 2),
                        "average_score": round(p1_total / len(logged_days), 2) if logged_days else 0,
                        "wins": p1_wins,
                        "losses": p2_wins,
                        "draws": draws,
                    },
                    p2_name: {
                        "total_points": round(p2_total, 2),
                        "average_score": round(p2_total / len(logged_days), 2) if logged_days else 0,
                        "wins": p2_wins,
                        "losses": p1_wins,
                        "draws": draws,
                    },
                },
            }

        return data

    @staticmethod
    def get_latest_logged_entry(data: dict[str, Any] = DEFAULT_COMPETITION_DATA) -> dict[str, Any] | None:
        """Finds the most recent entry with actual scores or logged activities."""
        daily = data.get("daily_tracker", [])
        for day in reversed(daily):
            abhi_score = day.get("Abhi", {}).get("score", 0) or 0
            ajay_score = day.get("Ajay", {}).get("score", 0) or 0
            if abhi_score > 0 or ajay_score > 0 or day.get("result", {}).get("winner"):
                return day
        return daily[-1] if daily else None

    @staticmethod
    def format_winner_today(data: dict[str, Any] = DEFAULT_COMPETITION_DATA) -> str:
        standings = data.get("competition_standings", {})
        latest_entry = CompetitionTrackerEngine.get_latest_logged_entry(data)
        
        if not latest_entry:
            winner = standings.get("today_winner", "Abhi")
            diff = standings.get("score_difference", 33.2)
            latest_date = "Today"
            p1_score = 56.3
            p2_score = 23.1
            p1_pct = "56.3%"
            p2_pct = "23.1%"
        else:
            winner = latest_entry.get("result", {}).get("winner") or standings.get("today_winner", "Abhi")
            diff = latest_entry.get("result", {}).get("point_diff") or standings.get("score_difference", 0.0)
            latest_date = CompetitionTrackerEngine.clean_date_str(latest_entry.get("date", "Today"))
            p1_score = latest_entry.get("Abhi", {}).get("score", 0)
            p2_score = latest_entry.get("Ajay", {}).get("score", 0)
            p1_pct = latest_entry.get("Abhi", {}).get("completion_pct", "0%")
            p2_pct = latest_entry.get("Ajay", {}).get("completion_pct", "0%")

        congrats_line = (
            f"<i>🔥 Great hustle by {winner}! Keep pushing, {'Ajay' if winner == 'Abhi' else 'Abhi'}! 💪</i>"
        )

        return (
            f"🏆 <b>TODAY'S WINNER: {winner.upper()}</b>\n\n"
            f"📅 <b>Date:</b> {latest_date}\n"
            f"🥇 <b>{winner}</b> won by a margin of <b>+{diff:.2f} pts</b>!\n\n"
            f"<b>📊 Scores Breakdown:</b>\n"
            f"• 👤 <b>Abhi:</b> {p1_score:.1f} pts ({p1_pct})\n"
            f"• 👤 <b>Ajay:</b> {p2_score:.1f} pts ({p2_pct})\n\n"
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
            f"👑 <b>Current Leader:</b> <b>{leader}</b> (+{diff:.2f} pts)\n",
        ]

        for player, stats in standings.items():
            rank_icon = "🥇" if player == leader else "🥈"
            lines.append(
                f"{rank_icon} <b>{player}</b>\n"
                f"  • <b>Total Points:</b> {stats.get('total_points', 0):.1f} pts\n"
                f"  • <b>Average Score:</b> {stats.get('average_score', 0):.1f} pts\n"
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
            target_date = CompetitionTrackerEngine.clean_date_str(date_str)
            for day in daily:
                if CompetitionTrackerEngine.clean_date_str(day.get("date")) == target_date:
                    entry = day
                    break
        if not entry:
            entry = CompetitionTrackerEngine.get_latest_logged_entry(data)

        if not entry:
            return "No logged tracker entries available."

        d_val = CompetitionTrackerEngine.clean_date_str(entry.get("date", "Recent"))
        abhi = entry.get("Abhi", {})
        ajay = entry.get("Ajay", {})
        res = entry.get("result", {})
        diff_val = res.get("point_diff", 0.0) or 0.0

        p1_wake = CompetitionTrackerEngine.clean_time_str(abhi.get("wake_time"))
        p1_sleep = CompetitionTrackerEngine.clean_time_str(abhi.get("sleep_time"))
        p2_wake = CompetitionTrackerEngine.clean_time_str(ajay.get("wake_time"))
        p2_sleep = CompetitionTrackerEngine.clean_time_str(ajay.get("sleep_time"))

        return (
            f"📅 <b>DAILY TRACKER LOG — {d_val}</b>\n\n"
            f"👤 <b>ABHI ({abhi.get('score', 0):.1f} pts — {abhi.get('completion_pct', '0%')}):</b>\n"
            f"• ⏰ <b>Wake:</b> {p1_wake} | <b>Sleep:</b> {p1_sleep}\n"
            f"• 📚 <b>Study:</b> {abhi.get('study_hrs', 0):.1f}h | 🗣 <b>English:</b> {abhi.get('english_hrs', 0):.1f}h\n"
            f"• 🏃 <b>Workout:</b> {'✅ Done' if abhi.get('workout') else '❌ Missed'} | 👣 <b>Steps:</b> {abhi.get('steps') or 0:,}\n"
            f"• 🍔 <b>No Junk Food:</b> {'✅ Clean' if not abhi.get('junk_food') else '❌ Consumed'}\n"
            f"• 📝 <b>Remarks:</b> <i>{abhi.get('remarks') or 'None'}</i>\n\n"
            f"👤 <b>AJAY ({ajay.get('score', 0):.1f} pts — {ajay.get('completion_pct', '0%')}):</b>\n"
            f"• ⏰ <b>Wake:</b> {p2_wake} | <b>Sleep:</b> {p2_sleep}\n"
            f"• 📚 <b>Study:</b> {ajay.get('study_hrs', 0):.1f}h | 🗣 <b>English:</b> {ajay.get('english_hrs', 0):.1f}h\n"
            f"• 🏃 <b>Workout:</b> {'✅ Done' if ajay.get('workout') else '❌ Missed'} | 👣 <b>Steps:</b> {ajay.get('steps') or 0:,}\n"
            f"• 🍔 <b>No Junk Food:</b> {'✅ Clean' if not ajay.get('junk_food') else '❌ Consumed'}\n"
            f"• 📝 <b>Remarks:</b> <i>{ajay.get('remarks') or 'None'}</i>\n\n"
            f"🏆 <b>Result:</b> <b>{res.get('winner', 'Draw')}</b> (+{diff_val:.2f} pts)"
        )

    @staticmethod
    def build_compact_competition_context(data: dict[str, Any] = DEFAULT_COMPETITION_DATA) -> str:
        """Returns a minimal, highly accurate context summary (~120 tokens) for LLM prompts."""
        standings = data.get("competition_standings", {})
        leader = standings.get("current_leader", "Abhi")
        diff = standings.get("score_difference", 33.2)
        st_abhi = standings.get("standings", {}).get("Abhi", {})
        st_ajay = standings.get("standings", {}).get("Ajay", {})

        latest = CompetitionTrackerEngine.get_latest_logged_entry(data) or {}
        d_val = CompetitionTrackerEngine.clean_date_str(latest.get("date", "2026-08-29"))
        abhi = latest.get("Abhi", {})
        ajay = latest.get("Ajay", {})
        winner = latest.get("result", {}).get("winner") or standings.get("today_winner", "Abhi")
        win_diff = latest.get("result", {}).get("point_diff") or diff

        p1_wake = CompetitionTrackerEngine.clean_time_str(abhi.get("wake_time"))
        p2_wake = CompetitionTrackerEngine.clean_time_str(ajay.get("wake_time"))

        return (
            f"[COMPETITION DATA CONTEXT (Abhi vs Ajay)]:\n"
            f"- Current Standings: Leader = {leader} (+{diff:.2f} pts). Abhi: {st_abhi.get('total_points', 0):.1f} pts ({st_abhi.get('wins', 0)}W), Ajay: {st_ajay.get('total_points', 0):.1f} pts ({st_ajay.get('wins', 0)}W).\n"
            f"- Latest Logged Entry ({d_val}):\n"
            f"  * Abhi: Score {abhi.get('score', 0):.1f}/100 ({abhi.get('completion_pct', '0%')}) | Wake: {p1_wake} | Study: {abhi.get('study_hrs', 0):.1f}h | English: {abhi.get('english_hrs', 0):.1f}h | Workout: {'Yes' if abhi.get('workout') else 'No'} | Steps: {abhi.get('steps', 0):,} | Remarks: '{abhi.get('remarks') or 'None'}'\n"
            f"  * Ajay: Score {ajay.get('score', 0):.1f}/100 ({ajay.get('completion_pct', '0%')}) | Wake: {p2_wake} | Study: {ajay.get('study_hrs', 0):.1f}h | English: {ajay.get('english_hrs', 0):.1f}h | Workout: {'Yes' if ajay.get('workout') else 'No'} | Steps: {ajay.get('steps', 0):,} | Remarks: '{ajay.get('remarks') or 'None'}'\n"
            f"  * Daily Result: Winner = {winner} (+{win_diff:.2f} pts)\n"
        )
