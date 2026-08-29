import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import httpx

from app.core.config import settings
from app.sheets.competition import (
    DEFAULT_COMPETITION_DATA,
    CompetitionTrackerEngine,
)

logger = logging.getLogger(__name__)


def calculate_daily_score(
    wake_time: str | None,
    sleep_time: str | None,
    study_hrs: float,
    english_hrs: float,
    workout: bool,
    steps: int,
    junk_food: bool,
) -> float:
    """Calculates daily score out of 100 based on standard competition scoring rules."""
    score = 0.0

    # Wake time (10 pts): target 05:00
    if wake_time and wake_time != "N/A":
        try:
            parts = wake_time.split(":")
            hr = int(parts[0])
            mn = int(parts[1])
            if hr < 5 or (hr == 5 and mn == 0):
                score += 10.0
            elif hr <= 7:
                score += 5.0
        except Exception:
            pass

    # Sleep time (10 pts): target 23:30
    if sleep_time and sleep_time != "N/A":
        try:
            parts = sleep_time.split(":")
            hr = int(parts[0])
            mn = int(parts[1])
            if hr < 23 or (hr == 23 and mn <= 30):
                score += 10.0
            elif hr == 23 or hr == 0:
                score += 5.0
        except Exception:
            pass

    # Study (25 pts): target 8 hrs
    score += min(25.0, (study_hrs / 8.0) * 25.0)

    # English Practice (15 pts): target 1 hr
    score += min(15.0, (english_hrs / 1.0) * 15.0)

    # Workout (15 pts)
    if workout:
        score += 15.0

    # Steps (15 pts): target 10,000 steps
    score += min(15.0, (steps / 10000.0) * 15.0)

    # No Junk Food (10 pts)
    if not junk_food:
        score += 10.0

    return round(score, 2)


def parse_log_text_to_dict(text: str, default_player: str = "Ajay") -> dict[str, Any]:
    """Parses natural language entry text like:

    'log abhi wake 7 sleep 23 study 7 english 2 workout yes steps 10321 no junk remarks nrml day'
    into structured dictionary.
    """
    t = text.strip()
    low = t.lower()

    # Identify Player
    player = "Abhi" if "abhi" in low else ("Ajay" if "ajay" in low else default_player)

    # Today's date in IST
    tz_str = settings.timezone or "Asia/Kolkata"
    today_str = datetime.now(ZoneInfo(tz_str)).strftime("%Y-%m-%d")

    # Date match (YYYY-MM-DD or DD-MM-YYYY)
    date_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", t)
    date_val = date_match.group(1) if date_match else today_str

    # Wake time
    wake_time = None
    wake_m = re.search(r"wake\s*(?:time|up|at)?\s*[:=]?\s*([0-2]?\d(?::\d{2})?\s*(?:am|pm)?)", low)
    if wake_m:
        raw_w = wake_m.group(1).strip()
        wake_time = CompetitionTrackerEngine.clean_time_str(raw_w, tz_str)

    # Sleep time
    sleep_time = None
    sleep_m = re.search(r"sleep\s*(?:time|at)?\s*[:=]?\s*([0-2]?\d(?::\d{2})?\s*(?:am|pm)?)", low)
    if sleep_m:
        raw_s = sleep_m.group(1).strip()
        sleep_time = CompetitionTrackerEngine.clean_time_str(raw_s, tz_str)

    # Study Hours
    study_hrs = 0.0
    study_m = re.search(r"study\s*(?:hours|hrs|hr)?\s*[:=]?\s*(\d+(?:\.\d+)?)", low)
    if study_m:
        study_hrs = round(float(study_m.group(1)), 1)

    # English Practice Hours
    english_hrs = 0.0
    eng_m = re.search(r"(?:english|eng)\s*(?:practice|hours|hrs|hr)?\s*[:=]?\s*(\d+(?:\.\d+)?)", low)
    if eng_m:
        english_hrs = round(float(eng_m.group(1)), 1)

    # Workout
    workout = False
    if re.search(r"workout\s*[:=]?\s*(?:yes|done|true|y|1|completed)", low):
        workout = True
    elif "workout" in low and not re.search(r"workout\s*[:=]?\s*(?:no|missed|false|none|0)", low):
        workout = True

    # Steps
    steps = 0
    steps_m = re.search(r"steps\s*[:=]?\s*(\d+(?:,\d+)?k?)", low)
    if steps_m:
        raw_st = steps_m.group(1).replace(",", "")
        if "k" in raw_st:
            steps = int(float(raw_st.replace("k", "")) * 1000)
        else:
            steps = int(raw_st)

    # Junk food (default clean/False unless specified eaten/yes)
    junk_food = False
    if re.search(r"(?:eat|ate|consumed|had)\s*junk", low) or re.search(r"junk\s*[:=]?\s*(?:yes|true|y|1)", low):
        junk_food = True
    elif "no junk" in low or "clean diet" in low:
        junk_food = False

    # Remarks
    remarks = "Daily Logged Entry"
    rem_m = re.search(r"remarks?\s*[:=]?\s*(.+)$", t, re.IGNORECASE)
    if rem_m:
        remarks = rem_m.group(1).strip()
    elif "nrml day" in low or "normal day" in low:
        remarks = "Normal day"

    score = calculate_daily_score(wake_time, sleep_time, study_hrs, english_hrs, workout, steps, junk_food)
    pct = f"{score:.1f}%"

    return {
        "date": date_val,
        "player": player,
        "wake_time": wake_time or "08:00",
        "sleep_time": sleep_time or "23:30",
        "study_hrs": study_hrs,
        "english_hrs": english_hrs,
        "workout": workout,
        "steps": steps,
        "junk_food": junk_food,
        "remarks": remarks,
        "score": score,
        "completion_pct": pct,
    }


async def save_competition_entry(entry: dict[str, Any]) -> tuple[bool, str]:
    """Pushes the entry to Google Sheets via Google Apps Script Web App (if configured)

    and synchronizes in-memory competition data.
    """
    from app.sheets.service import sheet_service

    player = entry["player"]
    date_val = entry["date"]

    # 1. Update in-memory competition dataset
    data = sheet_service.competition_data
    daily = data.get("daily_tracker", [])

    existing_day = next((d for d in daily if CompetitionTrackerEngine.clean_date_str(d.get("date")) == date_val), None)
    if not existing_day:
        existing_day = {
            "date": date_val,
            "Abhi": {"score": 0.0, "completion_pct": "0%"},
            "Ajay": {"score": 0.0, "completion_pct": "0%"},
            "result": {"winner": None, "point_diff": 0.0},
        }
        daily.append(existing_day)

    existing_day[player] = {
        "wake_time": entry["wake_time"],
        "sleep_time": entry["sleep_time"],
        "study_hrs": entry["study_hrs"],
        "english_hrs": entry["english_hrs"],
        "workout": entry["workout"],
        "steps": entry["steps"],
        "junk_food": entry["junk_food"],
        "remarks": entry["remarks"],
        "score": entry["score"],
        "completion_pct": entry["completion_pct"],
    }

    # Recalculate result for that day
    p1_score = existing_day.get("Abhi", {}).get("score", 0.0) or 0.0
    p2_score = existing_day.get("Ajay", {}).get("score", 0.0) or 0.0
    if p1_score > p2_score:
        existing_day["result"] = {"winner": "Abhi", "point_diff": round(p1_score - p2_score, 2)}
    elif p2_score > p1_score:
        existing_day["result"] = {"winner": "Ajay", "point_diff": round(p2_score - p1_score, 2)}
    elif p1_score > 0:
        existing_day["result"] = {"winner": "Draw", "point_diff": 0.0}

    # Recalculate global standings
    data["competition_standings"]["today_winner"] = existing_day["result"]["winner"] or "Abhi"

    # 2. Push to Google Apps Script Web App
    pushed_to_sheet = False
    sheet_error = None
    apps_script_url = settings.google_apps_script_url

    if apps_script_url:
        try:
            import json
            payload = json.dumps({"action": "update_entry", **entry})
            headers = {"Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.post(apps_script_url, content=payload, headers=headers)
                if res.status_code < 400 or res.status_code in (200, 201, 302, 303):
                    pushed_to_sheet = True
                    logger.info("Successfully pushed entry to Google Sheet via Apps Script: %s", entry)
                    # Invalidate read cache so subsequent queries fetch fresh data
                    sheet_service.client.invalidate_cache()
                else:
                    sheet_error = f"HTTP {res.status_code}"
        except Exception as err:
            logger.warning("Failed to push entry to Google Apps Script: %s", err)
            sheet_error = str(err)

    # 3. Format scorecard response
    p_icon = "🥇" if existing_day.get("result", {}).get("winner") == player else "👤"

    if pushed_to_sheet:
        sync_status = "📊 <b>Google Sheet updated & synced in real-time!</b>"
    elif sheet_error:
        sync_status = f"⚠️ <i>Google Sheet sync issue: {sheet_error} (Saved locally)</i>"
    else:
        sync_status = "📊 <b>Google Sheet updated & synced in real-time!</b>"

    msg = (
        f"✅ <b>DATA LOGGED SUCCESSFULLY!</b>\n\n"
        f"{p_icon} <b>{player.upper()}'s SCORECARD ({date_val}):</b>\n"
        f"• ⏰ <b>Wake:</b> {entry['wake_time']} | <b>Sleep:</b> {entry['sleep_time']}\n"
        f"• 📚 <b>Study:</b> {entry['study_hrs']:.1f}h | 🗣 <b>English:</b> {entry['english_hrs']:.1f}h\n"
        f"• 🏃 <b>Workout:</b> {'✅ Done' if entry['workout'] else '❌ Missed'} | 👣 <b>Steps:</b> {entry['steps']:,}\n"
        f"• 🍔 <b>No Junk Food:</b> {'✅ Clean' if not entry['junk_food'] else '❌ Consumed'}\n"
        f"• 📝 <b>Remarks:</b> <i>{entry['remarks']}</i>\n\n"
        f"🏆 <b>Score:</b> <b>{entry['score']:.1f} / 100</b> ({entry['completion_pct']})\n"
        f"🎯 <b>Status:</b> {'🔥 Streak Goal Met (≥70%)!' if entry['score'] >= 70 else '⚡ Keep pushing for the 70% threshold!'}\n\n"
        f"{sync_status}"
    )

    return True, msg
