import re
from datetime import datetime


_TIME_12H_PATTERN = re.compile(
    r"^(?P<hour>0?[1-9]|1[0-2])(?::(?P<minute>[0-5]\d))?\s*(?P<period>AM|PM)$",
    re.IGNORECASE,
)
_TIME_24H_PATTERN = re.compile(r"^(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)$")


def _normalize_spaces(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[\s\u00a0\u2000-\u200f\ufeff]+", " ", text).strip()


def parse_time_string(raw_time: str) -> tuple[str, str] | None:
    """Parses a time string in 24-hour (e.g. '16:04', '07:00') or 12-hour ('8:30 PM', '7 AM') format.

    Returns:
        tuple of (24h_format 'HH:MM', display_format 'HH:MM') or None if invalid.
    """
    if not raw_time:
        return None
    cleaned = _normalize_spaces(raw_time)

    # 1. Try 24-hour format: e.g. "16:04", "07:00", "7:00", "19:30", "00:00"
    match_24 = _TIME_24H_PATTERN.match(cleaned)
    if match_24:
        hour_24 = int(match_24.group("hour"))
        minute = int(match_24.group("minute"))
        time_24 = f"{hour_24:02d}:{minute:02d}"
        return time_24, time_24

    # 2. Try 12-hour format: e.g. "8:30 PM", "7 AM", "12:00 AM"
    match_12 = _TIME_12H_PATTERN.match(cleaned)
    if match_12:
        hour = int(match_12.group("hour"))
        minute = int(match_12.group("minute") or 0)
        period = match_12.group("period").upper()

        if period == "AM":
            hour_24 = 0 if hour == 12 else hour
        else:
            hour_24 = 12 if hour == 12 else hour + 12

        time_24 = f"{hour_24:02d}:{minute:02d}"
        return time_24, time_24

    return None


def parse_remainder_command(text: str) -> tuple[str, str, str] | None:
    """Extracts task name and 24-hour time from flexible user inputs like:

    'Study DSA 16:04'
    '/remainder Study DSA 16:04'
    'remind Go for gym 18:30'
    '/remind Study DSA 8:30 PM'
    'Read book 07:00'

    Returns:
        tuple of (task_name, time_24h, display_time_24h) or None.
    """
    if not text:
        return None

    normalized = _normalize_spaces(text)
    parts = normalized.split()

    # Strip command prefixes if present
    if parts and parts[0].lower().startswith(("/remainder", "/remind", "/reminder", "remainder", "remind")):
        parts = parts[1:]

    full_arg = " ".join(parts).strip()
    if not full_arg:
        return None

    words = full_arg.split()

    # Try 1-word time at the end (standard 24-hour: e.g. "16:04", "07:00", "19:30" or "8:30PM")
    if len(words) >= 2:
        potential_time_1w = words[-1]
        parsed = parse_time_string(potential_time_1w)
        if parsed:
            task_name = " ".join(words[:-1]).strip()
            if task_name:
                return task_name, parsed[0], parsed[1]

    # Try 2-word time at the end (12-hour: e.g. "8:30 PM", "7 AM")
    if len(words) >= 3:
        potential_time_2w = f"{words[-2]} {words[-1]}"
        parsed = parse_time_string(potential_time_2w)
        if parsed:
            task_name = " ".join(words[:-2]).strip()
            if task_name:
                return task_name, parsed[0], parsed[1]

    return None
