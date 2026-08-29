from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.database.models import User
from app.productivity.models import DailyProgress, StreakStats, TaskProgress
from app.news.sources import CATEGORY_DISPLAY_NAMES


def format_morning_message(user: User, tasks: list[TaskProgress], date_val: date, combined_news: bool = False) -> str:
    date_str = date_val.strftime("%A, %d %B %Y")
    
    task_lines = []
    for t in tasks:
        icon = "🎥" if t.task_type == "video" else ("📚" if t.task_type == "study" else ("🏃" if t.task_type == "exercise" else "📌"))
        target_str = f" — {t.target_value:g} {t.target_unit}" if t.target_unit != "done" else ""
        task_lines.append(f"{icon} {t.name}{target_str}")

    tasks_block = "\n".join(task_lines)

    if combined_news:
        return (
            f"☀️ <b>GOOD MORNING</b>\n\n"
            f"📅 <b>{date_str}</b>\n\n"
            f"🎯 <b>TODAY'S CHALLENGE</b>\n"
            f"{tasks_block}\n\n"
            f"📰 <b>TODAY'S NEWS</b>\n"
            f"🤖 AI — 5\n"
            f"🌍 World — 5\n"
            f"🍥 Anime — 5\n"
            f"🟡 Telugu — 5\n"
            f"🇮🇳 India — 5\n\n"
            f"Let's make today count. 💪"
        )

    return (
        f"☀️ <b>Good morning!</b>\n\n"
        f"Today's challenge starts now ({date_str}).\n\n"
        f"<b>Your tasks:</b>\n"
        f"{tasks_block}\n\n"
        f"Let's get it done. 💪"
    )


def format_tasks_overview(progress: DailyProgress) -> str:
    date_str = progress.day.strftime("%d %B %Y")
    lines = [
        f"📋 <b>TODAY'S TASKS — {date_str}</b>",
        f"📊 <b>Score:</b> {progress.total_score:g} / {progress.max_score:g} ({progress.completion_percentage:g}%)",
        f"🔥 <b>Current Streak:</b> {progress.streak_days} days\n",
    ]

    for t in progress.tasks:
        icon = "🎥" if t.task_type == "video" else ("📚" if t.task_type == "study" else ("🏃" if t.task_type == "exercise" else "📌"))
        if t.status == "completed":
            status_text = "✅ Completed"
        elif t.status == "skipped":
            status_text = "⏭ Skipped"
        elif t.actual_value > 0:
            status_text = f"⏱ In Progress ({t.actual_value:g}/{t.target_value:g} {t.target_unit})"
        else:
            status_text = "⏳ Pending"

        detail_lines = []
        if t.details:
            for k, v in t.details.items():
                if v:
                    detail_lines.append(f"  • {k.capitalize()}: {v}")
        if t.remarks:
            detail_lines.append(f"  • Remarks: {t.remarks}")

        lines.append(f"{icon} <b>{t.name}</b> ({t.points:g} pts)")
        lines.append(f"Status: {status_text} | Score: {t.score:g} pts")
        if detail_lines:
            lines.extend(detail_lines)
        lines.append("")

    return "\n".join(lines).strip()


def format_daily_summary(progress: DailyProgress) -> str:
    date_str = progress.day.strftime("%d %B %Y")
    lines = [
        "🌙 <b>DAILY SUMMARY</b>\n",
        f"📅 <b>Date:</b> {date_str}\n",
    ]

    for t in progress.tasks:
        icon = "🎥" if t.task_type == "video" else ("📚" if t.task_type == "study" else ("🏃" if t.task_type == "exercise" else "📌"))
        if t.status == "completed":
            lines.append(f"{icon} {t.name}: ✅")
        elif t.status == "skipped":
            lines.append(f"{icon} {t.name}: ⏭ Skipped")
        elif t.actual_value > 0:
            lines.append(f"{icon} {t.name}: {t.actual_value:g} / {t.target_value:g} {t.target_unit}")
        else:
            lines.append(f"{icon} {t.name}: ❌ Not completed")

    lines.append("")
    lines.append(f"📊 <b>Score:</b> {progress.total_score:g} / {progress.max_score:g}")
    lines.append(f"📈 <b>Completion:</b> {progress.completion_percentage:g}%")
    lines.append(f"🔥 <b>Current Streak:</b> {progress.streak_days} days\n")

    remarks_text = progress.remarks if progress.remarks else "None recorded."
    lines.append(f"📝 <b>Remarks:</b>\n{remarks_text}\n")

    lines.append("<b>Tomorrow's goal:</b>\nImprove today's missed/incomplete tasks. 🚀")
    return "\n".join(lines)


def format_missed_task_reminder(task: TaskProgress) -> str:
    icon = "🎥" if task.task_type == "video" else ("📚" if task.task_type == "study" else ("🏃" if task.task_type == "exercise" else "📌"))
    target_str = f"{task.target_value:g} {task.target_unit}" if task.target_unit != "done" else "Daily challenge"
    return (
        f"⏰ <b>Quick reminder</b>\n\n"
        f"You haven't marked today's <b>{task.name}</b> task as completed yet.\n\n"
        f"{icon} <b>Target:</b> {target_str}\n\n"
        f"You still have time. 💪"
    )


def format_streak_stats(stats: StreakStats) -> str:
    return (
        f"🔥 <b>STREAK & PERFORMANCE STATS</b>\n\n"
        f"🔥 <b>Current Streak:</b> {stats.current_streak} days\n"
        f"🏆 <b>Longest Streak:</b> {stats.longest_streak} days\n"
        f"✅ <b>Successful Days (>={stats.threshold:g}%):</b> {stats.total_successful_days} days\n"
        f"❌ <b>Missed Days:</b> {stats.missed_days} days\n"
        f"⭐ <b>Perfect (100%) Days:</b> {stats.perfect_days} days\n\n"
        f"🎯 <i>Qualifying threshold is set to {stats.threshold:g}% daily score.</i>"
    )


def format_times_overview(user: User) -> str:
    return (
        f"⏰ <b>CONFIGURED REMINDER TIMES</b>\n\n"
        f"🌍 <b>Timezone:</b> {user.timezone}\n\n"
        f"☀️ <b>Morning Challenge:</b> {user.morning_time}\n"
        f"📰 <b>Daily News Digest:</b> {user.news_time}\n"
        f"🎥 <b>Video Reminder:</b> {user.video_time}\n"
        f"📚 <b>Study Reminder:</b> {user.study_time}\n"
        f"🏃 <b>Exercise Reminder:</b> {user.exercise_time}\n"
        f"🌙 <b>End-of-Day Summary:</b> {user.eod_time}\n\n"
        f"<i>Use /settime &lt;type&gt; &lt;HH:MM&gt; or the settings menu to change any time.</i>"
    )


def format_settings_overview(user: User) -> str:
    return (
        f"⚙️ <b>BOT SETTINGS</b>\n\n"
        f"🌍 <b>Timezone:</b> {user.timezone}\n"
        f"🗣 <b>Language:</b> {user.language.upper()}\n"
        f"📰 <b>News Time:</b> {user.news_time}\n"
        f"⏰ <b>Morning Time:</b> {user.morning_time}\n"
        f"🔔 <b>Missed Task Nudges:</b> {'Enabled' if user.missed_reminders_enabled else 'Disabled'}\n"
        f"🚨 <b>Breaking News Alerts:</b> {'Enabled' if user.breaking_news_enabled else 'Disabled'}\n"
        f"☀️ <b>Combined Morning Msg:</b> {'Enabled' if user.morning_combined_enabled else 'Disabled'}\n"
        f"🔥 <b>Streak Threshold:</b> {user.streak_threshold:g}%\n\n"
        f"Tap the buttons below to customize your experience."
    )


def format_sources_overview(sources_dict: dict) -> str:
    lines = ["📰 <b>VERIFIED NEWS SOURCES & TIERS</b>\n"]
    tier_labels = {1: "Tier 1 (Official / Primary)", 2: "Tier 2 (High-Quality Journalism)", 3: "Tier 3 (Specialist)"}
    
    for cat, list_src in sources_dict.items():
        cat_title = CATEGORY_DISPLAY_NAMES.get(cat, cat.upper())
        lines.append(f"<b>{cat_title}</b>")
        for s in list_src:
            t_label = tier_labels.get(s["tier"], f"Tier {s['tier']}")
            lines.append(f"• <b>{s['name']}</b> [{t_label}]")
        lines.append("")
    
    lines.append("<i>Source hierarchy prioritizes primary & verified journalism over unverified social media.</i>")
    return "\n".join(lines)


def format_help_message() -> str:
    return (
        "🤖 <b>J.A.R.V.I.S. PROTOCOL GUIDE & COMMANDS</b>\n\n"
        "<b>Core Directives:</b>\n"
        "• <code>Study DSA 16:04</code> — Register scheduled reminder directive\n"
        "• <code>ask &lt;query&gt;</code> — Instant intelligence lookup (Multi-LLM)\n"
        "• <code>/reminders</code> — View & manage all active directives\n"
        "• <code>/deleteremainder &lt;id&gt;</code> — Terminate a reminder\n\n"
        "<b>📊 Competition Tracker (Abhi vs Ajay):</b>\n"
        "• <code>/sheet</code> — Interactive Competition Dashboard & Winner\n"
        "• <code>sheet &lt;query&gt;</code> — Ask any question (e.g. <code>sheet who is the winner today</code>)\n\n"
        "<b>Intelligence Feeds:</b>\n"
        "• <code>/news</code> — Complete 25-item Daily Intelligence Digest\n"
        "• <code>/news 5</code> — Compact top 5 intelligence briefing\n"
        "• <code>/ai</code> — 5 verified AI & infrastructure developments\n"
        "• <code>/world</code> — 5 Geography & Geopolitical developments\n"
        "• <code>/anime</code> — 5 verified Anime & cultural updates\n"
        "• <code>/telugu</code> — 5 Andhra Pradesh & Telangana updates\n"
        "• <code>/india</code> — 5 Indian national developments\n"
        "• <code>/sources</code> — View verified sources & trust tiers\n\n"
        "<b>System Diagnostics & Settings:</b>\n"
        "• <code>/status</code> — System health & neural diagnostics\n"
        "• <code>/settings</code> — Configure chronometer & protocols\n"
        "• <code>/timezone &lt;Zone&gt;</code> — Set local timezone (e.g. <code>Asia/Kolkata</code>)\n\n"
        "<i>At your service, sir.</i>"
    )

