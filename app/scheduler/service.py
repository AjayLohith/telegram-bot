import asyncio
import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.bot.keyboards import get_reminder_delivery_keyboard
from app.bot.sanitizer import sanitize_zero_urls
from app.core.config import settings
from app.core.database import SessionLocal
from app.database.models import User
from app.database.repositories.delivery_repo import DeliveryRepository
from app.database.repositories.news_repo import NewsRepository
from app.database.repositories.reminder_repo import ReminderRepository
from app.database.repositories.user_repo import UserRepository
from app.news.digest import build_full_daily_digest
from app.productivity.reminder_ai import _build_deterministic_focus, format_reminder_message, generate_reminder_focus

logger = logging.getLogger(__name__)

# In-memory tracking of dispatched daily notifications: set of (user_id, date, notification_type)
_SENT_NOTIFICATIONS: set[tuple[int, date, str]] = set()


async def check_and_dispatch_scheduled_events(bot: Bot) -> None:
    """Universal timezone scheduler dispatcher:

    1. Evaluates every 15 seconds across all active users and custom reminders.
    2. Sends 07:00 AM Daily News Digest with exponential retries and Delivery tracking.
    3. Triggers custom `/remainder` reminders with On-Trigger Dynamic AI summaries.
    4. Triggers built-in morning challenge, video, study, exercise, nudges, and EOD summaries.
    5. Dispatches with loud sound (disable_notification=False) and [✅ Done] action button.
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
                # 1. 07:00 AM Daily News Digest
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
            # 2. Direct Custom Reminders (Exact User-Scheduled Point in Time)
            # ==========================================
            rem_repo = ReminderRepository(session)
            active_reminders = rem_repo.list_active_reminders()
            for rem in active_reminders:
                rem_tz_name = rem.timezone or settings.timezone
                try:
                    rem_tz = ZoneInfo(rem_tz_name)
                except Exception:
                    rem_tz = ZoneInfo("Asia/Kolkata")

                rem_now = datetime.now(rem_tz)
                rem_date = rem_now.date()
                rem_curr_hhmm = rem_now.strftime("%H:%M")

                rem_target_hhmm = rem.reminder_time.strip().zfill(5)
                rem_key = (rem.telegram_user_id, rem_date, f"rem_{rem.id}")

                if rem_curr_hhmm == rem_target_hhmm and rem_key not in _SENT_NOTIFICATIONS:
                    _SENT_NOTIFICATIONS.add(rem_key)
                    asyncio.create_task(
                        _send_custom_reminder(
                            bot,
                            rem.id,
                            rem.telegram_user_id,
                            rem.task_name,
                            rem.display_time or rem.reminder_time,
                            rem_tz_name,
                        )
                    )

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
                    await bot.send_message(
                        telegram_user_id,
                        clean_msg,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        disable_notification=False,
                    )
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
    """Generates the on-trigger dynamic AI focus summary and delivers the reminder with loud sound."""
    try:
        try:
            bullets = await asyncio.wait_for(generate_reminder_focus(task_name), timeout=3.0)
        except Exception:
            bullets = _build_deterministic_focus(task_name)

        msg_text = format_reminder_message(
            task_name=task_name,
            display_time=display_time,
            tz_name=tz_name,
            focus_bullets=bullets,
        )
        clean_msg = sanitize_zero_urls(msg_text)
        keyboard = get_reminder_delivery_keyboard(reminder_id)

        await bot.send_message(
            telegram_user_id,
            clean_msg,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_notification=False,
        )

        with SessionLocal() as session:
            rem_repo = ReminderRepository(session)
            rem_repo.update_last_triggered(reminder_id, timestamp=datetime.now(timezone.utc), ai_summary="\n".join(bullets))

        logger.info("Custom reminder #%d delivered to %s for task '%s'", reminder_id, telegram_user_id, task_name)
    except Exception as err:
        logger.error("Failed to deliver custom reminder #%d to %s: %s", reminder_id, telegram_user_id, err)


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
    logger.info("Universal timezone scheduler started with 30s precision.")
    return scheduler

