import logging
from datetime import datetime, timezone
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.formatters import format_morning_message, format_sources_overview
from app.bot.keyboards import get_admin_keyboard, get_cancel_keyboard
from app.bot.states import BroadcastState
from app.core.config import settings
from app.core.database import SessionLocal
from app.database.models import DailySummary, NewsArticle, Task, User
from app.database.repositories.user_repo import UserRepository
from app.news.digest import build_full_daily_digest
from app.news.service import NewsService
from app.productivity.service import ProductivityService

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def admin_dashboard(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied. Admin privileges required.")
        return

    with SessionLocal() as session:
        user_count = len(session.query(User).all())
        article_count = len(session.query(NewsArticle).all())
        user = UserRepository(session).get_by_telegram_id(message.from_user.id)
        is_paused = user.is_paused if user else False

    text = (
        f"🛠 <b>ADMIN CONTROL PANEL</b>\n\n"
        f"👥 Total Users: {user_count}\n"
        f"📰 Cached News Articles: {article_count}\n"
        f"⚙️ Bot Status: {'⏸ Paused' if is_paused else '▶️ Active'}\n\n"
        f"Select an administrative action below:"
    )
    keyboard = get_admin_keyboard(is_paused=is_paused)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("admin_sources"))
@router.callback_query(F.data == "admin_sources_view")
async def admin_sources_cmd(event: Message | CallbackQuery) -> None:
    user_id = event.from_user.id
    if not is_admin(user_id):
        if isinstance(event, CallbackQuery):
            await event.answer("Access denied.", show_alert=True)
        return

    with SessionLocal() as session:
        summary = NewsService(session).get_sources_summary()
        text = format_sources_overview(summary)

    if isinstance(event, CallbackQuery):
        await event.message.answer(text, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML")


@router.message(Command("admin_testnews"))
@router.callback_query(F.data == "admin_test_news")
async def admin_test_news_cmd(event: Message | CallbackQuery) -> None:
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    msg = event.message if isinstance(event, CallbackQuery) else event
    status = await msg.answer("🧪 [Admin] Generating test 25-item news digest...")
    with SessionLocal() as session:
        sections = await build_full_daily_digest(session)
    await status.delete()

    for sec in sections:
        if sec.strip():
            await msg.answer(sec, parse_mode="HTML", disable_web_page_preview=True)

    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("admin_testreminder"))
@router.callback_query(F.data == "admin_test_reminders")
async def admin_test_reminder_cmd(event: Message | CallbackQuery) -> None:
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    msg = event.message if isinstance(event, CallbackQuery) else event
    with SessionLocal() as session:
        user_repo = UserRepository(session)
        user, _ = user_repo.get_or_create(user_id, event.from_user.username)
        service = ProductivityService(session)
        today = datetime.now(timezone.utc).date()
        progress = service.get_daily_progress(user.id, today)
        morning_msg = format_morning_message(user, progress.tasks, today)

    await msg.answer(f"🧪 <b>[Admin Test Reminder]</b>\n\n{morning_msg}", parse_mode="HTML")
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("admin_stats"))
@router.callback_query(F.data == "admin_stats_view")
async def admin_stats_cmd(event: Message | CallbackQuery) -> None:
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    msg = event.message if isinstance(event, CallbackQuery) else event
    with SessionLocal() as session:
        user_count = len(session.query(User).all())
        task_count = len(session.query(Task).all())
        summary_count = len(session.query(DailySummary).all())
        article_count = len(session.query(NewsArticle).all())

    stats_text = (
        f"📊 <b>SYSTEM & DATABASE STATISTICS</b>\n\n"
        f"👥 Registered Users: {user_count}\n"
        f"📋 Configured Tasks: {task_count}\n"
        f"🌙 Daily Summaries Logged: {summary_count}\n"
        f"📰 Total News Articles in Cache: {article_count}\n"
        f"🕒 Server Time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await msg.answer(stats_text, parse_mode="HTML")
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("admin_broadcast"))
@router.callback_query(F.data == "admin_broadcast_start")
async def admin_broadcast_cmd(event: Message | CallbackQuery, state: FSMContext) -> None:
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    msg = event.message if isinstance(event, CallbackQuery) else event
    await state.set_state(BroadcastState.waiting_for_message)
    await msg.answer("📢 Send the message you wish to broadcast to all active users:", reply_markup=get_cancel_keyboard())
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    b_text = message.text or ""
    with SessionLocal() as session:
        users = UserRepository(session).list_active_users()

    sent_count = 0
    for u in users:
        try:
            await message.bot.send_message(u.telegram_id, f"📢 <b>ANNOUNCEMENT</b>\n\n{b_text}", parse_mode="HTML")
            sent_count += 1
        except Exception as e:
            logger.warning("Failed to broadcast to %s: %s", u.telegram_id, e)

    await state.clear()
    await message.answer(f"✅ Broadcast delivered to {sent_count}/{len(users)} users.")


@router.message(Command("admin_pause"))
@router.callback_query(F.data == "admin_pause")
async def admin_pause_cmd(event: Message | CallbackQuery) -> None:
    if not is_admin(event.from_user.id):
        return
    with SessionLocal() as session:
        UserRepository(session).update_settings(event.from_user.id, is_paused=True)
    msg = event.message if isinstance(event, CallbackQuery) else event
    await msg.answer("⏸ Bot notifications and reminders paused for this user/admin.")
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("admin_resume"))
@router.callback_query(F.data == "admin_resume")
async def admin_resume_cmd(event: Message | CallbackQuery) -> None:
    if not is_admin(event.from_user.id):
        return
    with SessionLocal() as session:
        UserRepository(session).update_settings(event.from_user.id, is_paused=False)
    msg = event.message if isinstance(event, CallbackQuery) else event
    await msg.answer("▶️ Bot notifications and reminders resumed.")
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("admin_logs"))
async def admin_logs_cmd(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer("📋 Application logs are directed to stdout and monitored in Docker container logs.")


@router.message(Command("admin_test7am"))
async def admin_test_7am_cmd(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    status_msg = await message.answer("🧪 [Admin] Testing 07:00 AM news delivery pipeline...")
    with SessionLocal() as session:
        sections = await build_full_daily_digest(session)
    await status_msg.delete()

    for sec in sections:
        if sec.strip():
            await message.answer(sec, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("admin_newsstatus"))
async def admin_news_status_cmd(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    with SessionLocal() as session:
        from app.database.repositories.delivery_repo import DeliveryRepository
        del_repo = DeliveryRepository(session)
        last_7am = del_repo.get_last_successful_7am_delivery()
        total_arts = len(session.query(NewsArticle).all())
        verified_arts = len(session.query(NewsArticle).filter_by(verification_status="verified").all())
        last_7am_str = last_7am.strftime("%Y-%m-%d %H:%M:%S UTC") if last_7am else "None yet"

    text = (
        f"📰 <b>NEWS PIPELINE STATUS</b>\n\n"
        f"⏰ Target Delivery: 07:00 AM IST\n"
        f"📅 Last Successful 7 AM Delivery: {last_7am_str}\n"
        f"📊 Verified Articles in DB: {verified_arts}/{total_arts}\n"
        f"🔒 Zero-URL Filter: ACTIVE (Strict)\n"
        f"🛡️ Deduplication Engine: ACTIVE"
    )
    await message.answer(text, parse_mode="HTML")

