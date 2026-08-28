import asyncio
import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.bot.formatters import format_daily_summary, format_missed_task_reminder, format_morning_message
from app.bot.keyboards import get_tasks_inline_keyboard
from app.bot.sanitizer import sanitize_zero_urls
from app.core.config import settings
from app.core.database import SessionLocal
from app.database.models import User
from app.database.repositories.delivery_repo import DeliveryRepository
from app.database.repositories.news_repo import NewsRepository
from app.database.repositories.reminder_repo import ReminderRepository
from app.database.repositories.user_repo import UserRepository
from app.news.digest import build_full_daily_digest
from app.productivity.reminder_ai import format_reminder_message, generate_reminder_focus
from app.productivity.service import ProductivityService

logger = logging.getLogger(__name__)

# In-memory tracking of dispatched daily notifications: set of (user_id, date, notification_type)
_SENT_NOTIFICATIONS: set[tuple[int, date, str]] = set()


async def check_and_dispatch_scheduled_events(bot: Bot) -> None:
    """Universal timezone scheduler dispatcher:

    1. Evaluates every 30 seconds across each active user's local timezone.
    2. Sends 07:00 AM Daily News Digest with exponential retries and Delivery tracking.
    3. Triggers custom `/remainder` reminders with On-Trigger Dynamic AI summaries.
    4. Triggers built-in morning challenge, video, study, exercise, nudges, and EOD summaries.
    5. Recovers seamlessly after restarts and avoids duplicates.
    """
    try:
        with SessionLocal() as session:
            user_repo = UserRepository(session)
            users = user_repo.list_active_users()
            if not users and settings.telegram_owner_id:
                user_repo.get_or_create(settings.telegram_owner_id)
                users = user_repo.list_active_users()

            for user in users:
                if user.is_paused:
                    continue

                tz_name = user.timezone or settings.timezone
                try:
                    user_tz = ZoneInfo(tz_name)
                except Exception:
                    user_tz = ZoneInfo("Asia/Kolkata")

                user_now = datetime.now(user_tz)
                user_date = user_now.date()
                curr_hhmm = user_now.strftime("%H:%M")

                # ==========================================
                # 1. 07:00 AM Daily News Digest (Prompt Section 4 & 5)
                # ==========================================
                # Pre-warm news cache at 06:55 so 07:00 delivery has 0s latency
                if curr_hhmm == "06:55" and (user.id, user_date, "news_prewarm") not in _SENT_NOTIFICATIONS:
                    from app.news.service import NewsService
                    news_svc = NewsService(session)
                    asyncio.create_task(news_svc.refresh_all())
                    _SENT_NOTIFICATIONS.add((user.id, user_date, "news_prewarm"))

                if curr_hhmm == user.news_time and (user.id, user_date, "news") not in _SENT_NOTIFICATIONS:
                    delivery_repo = DeliveryRepository(session)
                    if not delivery_repo.is_already_sent(user.telegram_id, user_date, digest_type="production"):
                        asyncio.create_task(_send_daily_news_with_retry(bot, user.telegram_id, user.id, user.language, user_date))
                    _SENT_NOTIFICATIONS.add((user.id, user_date, "news"))


                # ==========================================
                # 2. Custom /remainder Reminders (Prompt Section 25 & 30)
                # ==========================================
                rem_repo = ReminderRepository(session)
                user_reminders = rem_repo.list_active_reminders(user.telegram_id)
                for rem in user_reminders:
                    rem_key = (user.id, user_date, f"rem_{rem.id}")
                    if curr_hhmm == rem.reminder_time and rem_key not in _SENT_NOTIFICATIONS:
                        asyncio.create_task(_send_custom_reminder(bot, rem.id, user.telegram_id, rem.task_name, rem.display_time or rem.reminder_time, tz_name))
                        _SENT_NOTIFICATIONS.add(rem_key)

                # ==========================================
                # 3. Built-in Morning Challenge (08:00 AM)
                # ==========================================
                if curr_hhmm == user.morning_time and (user.id, user_date, "morning") not in _SENT_NOTIFICATIONS:
                    await _send_morning_challenge(bot, session, user, user_date)
                    _SENT_NOTIFICATIONS.add((user.id, user_date, "morning"))

                # ==========================================
                # 4. Built-in Task Reminders
                # ==========================================
                if curr_hhmm == user.video_time and (user.id, user_date, "task_video") not in _SENT_NOTIFICATIONS:
                    await _send_task_reminder(bot, session, user, user_date, "video", "🎥 Video Time", "Time to watch your educational/learning video! 🎥")
                    _SENT_NOTIFICATIONS.add((user.id, user_date, "task_video"))

                if curr_hhmm == user.study_time and (user.id, user_date, "task_study") not in _SENT_NOTIFICATIONS:
                    await _send_task_reminder(bot, session, user, user_date, "study", "📚 Study Time", "Time to hit the books and focus on your study target! 📚")
                    _SENT_NOTIFICATIONS.add((user.id, user_date, "task_study"))

                if curr_hhmm == user.exercise_time and (user.id, user_date, "task_exercise") not in _SENT_NOTIFICATIONS:
                    await _send_task_reminder(bot, session, user, user_date, "exercise", "🏃 Exercise Time", "Time to get moving and crush your workout! 🏃")
                    _SENT_NOTIFICATIONS.add((user.id, user_date, "task_exercise"))

                # ==========================================
                # 5. Missed Task Nudges (19:30)
                # ==========================================
                if user.missed_reminders_enabled and (user.id, user_date, "missed_check") not in _SENT_NOTIFICATIONS:
                    if curr_hhmm == "19:30":
                        await _send_missed_task_nudges(bot, session, user, user_date)
                        _SENT_NOTIFICATIONS.add((user.id, user_date, "missed_check"))

                # ==========================================
                # 6. End-of-Day Summary & Remarks (21:00)
                # ==========================================
                if curr_hhmm == user.eod_time and (user.id, user_date, "eod") not in _SENT_NOTIFICATIONS:
                    await _send_eod_summary(bot, session, user, user_date)
                    _SENT_NOTIFICATIONS.add((user.id, user_date, "eod"))

    except Exception as err:
        logger.error("Error in scheduler periodic dispatcher: %s", err, exc_info=True)


async def _send_daily_news_with_retry(
    bot: Bot,
    telegram_user_id: int,
    user_id: int,
    language: str,
    user_date: date,
) -> None:
    """Executes 7:00 AM news delivery with exponential backoff retries and delivery state tracking."""
    max_attempts = getattr(settings, "news_retry_max_attempts", 5)
    backoff_delays = getattr(settings, "news_retry_backoff_seconds", [0, 5, 15, 30, 60])

    with SessionLocal() as session:
        delivery_repo = DeliveryRepository(session)
        delivery, _ = delivery_repo.get_or_create_delivery(telegram_user_id, user_date, scheduled_time=settings.news_time, digest_type="production")
        delivery_id = delivery.id
        delivery_repo.update_status(delivery_id, "FETCHING")

    for attempt in range(max_attempts):
        delay = backoff_delays[attempt] if attempt < len(backoff_delays) else backoff_delays[-1]
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            with SessionLocal() as session:
                delivery_repo = DeliveryRepository(session)
                delivery_repo.update_status(delivery_id, "GENERATED", retry_count=attempt)
                sections = await build_full_daily_digest(session, language=language)

            for sec in sections:
                if sec.strip():
                    clean_msg = sanitize_zero_urls(sec)
                    await bot.send_message(telegram_user_id, clean_msg, parse_mode="HTML", disable_web_page_preview=True)
                    await asyncio.sleep(0.3)

            with SessionLocal() as session:
                delivery_repo = DeliveryRepository(session)
                delivery_repo.update_status(delivery_id, "SENT", retry_count=attempt)
                news_repo = NewsRepository(session)
                news_repo.record_digest(user_id, user_date, "all", [1])

            logger.info("Daily news digest successfully delivered at 07:00 AM to %s (attempt %d)", telegram_user_id, attempt + 1)
            return

        except Exception as e:
            logger.warning("Attempt %d failed to deliver 7 AM news to %s: %s", attempt + 1, telegram_user_id, e)
            with SessionLocal() as session:
                delivery_repo = DeliveryRepository(session)
                delivery_repo.update_status(delivery_id, "FAILED" if attempt == max_attempts - 1 else "VALIDATING", retry_count=attempt + 1)


async def _send_custom_reminder(
    bot: Bot,
    reminder_id: int,
    telegram_user_id: int,
    task_name: str,
    display_time: str,
    tz_name: str,
) -> None:
    """Generates the on-trigger dynamic AI focus summary and delivers the reminder."""
    try:
        bullets = await generate_reminder_focus(task_name)
        msg_text = format_reminder_message(
            task_name=task_name,
            display_time=display_time,
            tz_name=tz_name,
            focus_bullets=bullets,
        )
        clean_msg = sanitize_zero_urls(msg_text)
        await bot.send_message(telegram_user_id, clean_msg, parse_mode="HTML")

        with SessionLocal() as session:
            rem_repo = ReminderRepository(session)
            rem_repo.update_last_triggered(reminder_id, timestamp=datetime.now(timezone.utc), ai_summary="\n".join(bullets))

        logger.info("Custom reminder #%d delivered to %s for task '%s'", reminder_id, telegram_user_id, task_name)
    except Exception as err:
        logger.error("Failed to deliver custom reminder #%d to %s: %s", reminder_id, telegram_user_id, err)


async def _send_morning_challenge(bot: Bot, session, user: User, user_date: date) -> None:
    try:
        service = ProductivityService(session)
        progress = service.get_daily_progress(user.id, user_date)
        msg_text = format_morning_message(user, progress.tasks, user_date, combined_news=user.morning_combined_enabled)
        clean_msg = sanitize_zero_urls(msg_text)
        keyboard = get_tasks_inline_keyboard(progress.tasks)
        await bot.send_message(user.telegram_id, clean_msg, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.warning("Failed to send morning challenge to %s: %s", user.telegram_id, e)


async def _send_task_reminder(bot: Bot, session, user: User, user_date: date, task_type: str, title: str, subtitle: str) -> None:
    try:
        service = ProductivityService(session)
        progress = service.get_daily_progress(user.id, user_date)
        task = next((t for t in progress.tasks if t.task_type == task_type), None)
        if not task or task.is_completed or task.is_skipped:
            return

        keyboard = get_tasks_inline_keyboard(progress.tasks)
        text = sanitize_zero_urls(f"<b>{title}</b>\n\n{subtitle}\n\nTarget: {task.target_value:g} {task.target_unit}")
        await bot.send_message(user.telegram_id, text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.warning("Failed to send task reminder (%s) to %s: %s", task_type, user.telegram_id, e)


async def _send_missed_task_nudges(bot: Bot, session, user: User, user_date: date) -> None:
    try:
        service = ProductivityService(session)
        missed = service.get_missed_tasks(user.id, user_date)
        if not missed:
            return

        for m in missed:
            nudge = sanitize_zero_urls(format_missed_task_reminder(m))
            await bot.send_message(user.telegram_id, nudge, parse_mode="HTML")
            await asyncio.sleep(0.3)
    except Exception as e:
        logger.warning("Failed to send missed task nudge to %s: %s", user.telegram_id, e)


async def _send_eod_summary(bot: Bot, session, user: User, user_date: date) -> None:
    try:
        service = ProductivityService(session)
        progress = service.save_eod_summary(user.id, user_date)
        summary_text = sanitize_zero_urls(format_daily_summary(progress))
        await bot.send_message(user.telegram_id, summary_text, parse_mode="HTML")
    except Exception as e:
        logger.warning("Failed to send EOD summary to %s: %s", user.telegram_id, e)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone.utc)
    scheduler.add_job(
        check_and_dispatch_scheduled_events,
        IntervalTrigger(seconds=30),
        args=[bot],
        id="periodic_scheduler_dispatcher",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Universal timezone scheduler started.")
    return scheduler
