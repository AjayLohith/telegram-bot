import logging
from app.ai.http_providers import configured_providers
from app.ai.providers import AIRouter, ProviderError
from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_ai_router() -> AIRouter | None:
    providers = configured_providers(settings)
    if not providers:
        return None
    preference = [name for name in ("groq", "gemini", "mistral", "openai") if name in providers]
    return AIRouter(providers, {"reminder_summary": preference}) if preference else None


async def generate_reminder_focus(task_name: str) -> list[str]:
    """Generates a concise 2-3 bullet point 'Quick focus' summary for a reminder.

    Falls back deterministically if no AI provider is configured or on error.
    """
    router_ai = _get_ai_router()
    if router_ai is None:
        return _build_deterministic_focus(task_name)

    prompt = (
        f"Generate a concise, motivating focus checklist for the task: '{task_name}'.\n"
        f"STRICT RULES:\n"
        f"1. Return exactly 2 or 3 short, actionable bullet points.\n"
        f"2. Do not invent what the user has already done.\n"
        f"3. Do not include markdown headers or greetings.\n"
        f"4. Format each line starting with '* '.\n"
        f"Example:\n"
        f"* Spend focused time reviewing core concepts.\n"
        f"* Avoid distractions during this session.\n"
        f"* Make steady progress on today's target."
    )

    try:
        raw_response = await router_ai.complete("reminder_summary", prompt)
        lines = [line.strip() for line in raw_response.splitlines() if line.strip()]
        bullets = []
        for line in lines:
            if line.startswith(("*", "-", "•")):
                cleaned = line.lstrip("*-• ").strip()
                if cleaned:
                    bullets.append(cleaned)
            elif len(line) > 5 and not line.lower().startswith(("quick focus", "task")):
                bullets.append(line)
        if 1 <= len(bullets) <= 4:
            return bullets[:3]
    except Exception as err:
        logger.warning("AI reminder summary generation failed for '%s': %s", task_name, err)

    return _build_deterministic_focus(task_name)


def _build_deterministic_focus(task_name: str) -> list[str]:
    t_lower = task_name.lower()
    if "study" in t_lower or "read" in t_lower or "learn" in t_lower or "dsa" in t_lower:
        return [
            f"Spend focused time reviewing {task_name}.",
            "Avoid distractions and maintain deep concentration.",
            "Complete today's planned session and take concise notes.",
        ]
    elif "exercise" in t_lower or "workout" in t_lower or "gym" in t_lower or "run" in t_lower:
        return [
            f"Get ready for your {task_name} session.",
            "Stay hydrated and maintain proper form throughout.",
            "Finish strong and hit your target duration.",
        ]
    elif "video" in t_lower or "watch" in t_lower:
        return [
            f"Focus on the key insights from {task_name}.",
            "Note down one practical takeaway you can apply.",
        ]
    return [
        f"Dedicate uninterrupted time to {task_name}.",
        "Stay focused on the highest priority steps.",
        "Make steady progress toward today's goal.",
    ]


def format_reminder_message(task_name: str, display_time: str, tz_name: str, focus_bullets: list[str]) -> str:
    bullet_text = "\n".join(f"• {b}" for b in focus_bullets)
    time_str = f"{display_time} {tz_name}" if display_time else f"{tz_name}"
    return (
        f"🎯 <b>DIRECTIVE REMINDER // J.A.R.V.I.S.</b>\n\n"
        f"<b>Task:</b> {task_name}\n\n"
        f"<b>Tactical Focus:</b>\n"
        f"{bullet_text}\n\n"
        f"Scheduled: <b>{time_str}</b>\n\n"
        f"<i>At your service, sir. Let's make this session count.</i>"
    )


