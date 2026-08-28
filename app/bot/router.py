import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.ai.ask_service import ask_fast_answer
from app.ai.http_providers import configured_providers
from app.ai.providers import AIRouter, ProviderError
from app.bot.formatters import format_help_message
from app.bot.handlers import admin, news, productivity, settings as settings_handler
from app.bot.keyboards import get_clean_dashboard_keyboard, get_main_reply_keyboard
from app.core.config import settings
from app.core.database import SessionLocal
from app.database.repositories.reminder_repo import ReminderRepository
from app.database.repositories.user_repo import UserRepository
from app.memory.repository import MemoryRepository

logger = logging.getLogger(__name__)

# Base router for core top-level commands
base_router = Router()
fallback_router = Router()


@base_router.message(Command("start"))
async def start_handler(message: Message) -> None:
    with SessionLocal() as session:
        user_repo = UserRepository(session)
        user, _ = user_repo.get_or_create(message.from_user.id, message.from_user.username)
        rem_repo = ReminderRepository(session)
        reminders = rem_repo.list_active_reminders(message.from_user.id)
        user_tz = user.timezone or settings.timezone

    welcome_text = (
        f"🤖 <b>J.A.R.V.I.S. PROTOCOLS ONLINE</b>\n\n"
        f"Good day, sir. All neural diagnostics, task schedulers, and intelligence feeds are fully operational.\n\n"
        f"📰 <b>Daily Intelligence Briefing:</b> 07:00 AM IST\n"
        f"⏰ <b>Active Directives:</b> {len(reminders)}\n"
        f"🌍 <b>Chronometer:</b> {user_tz}\n\n"
        f"<b>Tactical Commands:</b>\n"
        f"• <code>Study DSA 16:04</code> — Set reminder directive (24h or 12h)\n"
        f"• <code>ask &lt;query&gt;</code> — Instant 1-line intelligence lookup\n"
        f"• <code>reminders</code> — View & manage your directives\n"
        f"• <code>news</code> — 25-item Verified Intelligence Digest\n"
        f"• <code>settings</code> — Configure core protocols"
    )
    clean_dashboard_kb = get_clean_dashboard_keyboard()
    await message.answer(welcome_text, reply_markup=get_main_reply_keyboard(), parse_mode="HTML")
    await message.answer("⚡ <b>Tactical Interface:</b>", reply_markup=clean_dashboard_kb, parse_mode="HTML")


@base_router.message(Command("ask"))
@base_router.message(F.text.startswith(("/ask", "ask ")))
async def ask_command(message: Message) -> None:
    raw = message.text or ""
    if raw.lower().startswith("/ask"):
        query = raw.partition(" ")[2].strip()
    elif raw.lower().startswith("ask "):
        query = raw[4:].strip()
    else:
        query = raw.strip()

    if not query or query == "/ask":
        await message.answer(
            "💬 <b>J.A.R.V.I.S. Intelligence Query</b>\n\n"
            "Usage: <code>/ask What is the speed of light?</code>\n"
            "or simply: <code>ask What is quantum computing?</code>\n\n"
            "<i>I will provide a concise, single-sentence response, sir.</i>",
            parse_mode="HTML",
        )
        return

    status = await message.answer("💭 Processing query, sir...")
    answer = await ask_fast_answer(query)
    try:
        await status.delete()
    except Exception:
        pass
    await message.answer(f"⚡ {answer}")


@base_router.message(F.text == "❓ Ask AI")
async def ask_ai_button(message: Message) -> None:
    await message.answer(
        "💬 <b>J.A.R.V.I.S. at your service, sir.</b>\n\n"
        "Ask any question directly or use:\n"
        "• <code>ask What is quantum computing?</code>\n"
        "• <code>/ask Explain neural networks in 1 line</code>\n\n"
        "<i>Delivers fast, high-accuracy 1-line intel.</i>",
        parse_mode="HTML",
    )


@base_router.message(Command("help"))
async def help_handler(message: Message) -> None:
    text = format_help_message()
    await message.answer(text, parse_mode="HTML")


@base_router.message(Command("status"))
async def status_handler(message: Message) -> None:
    with SessionLocal() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_telegram_id(message.from_user.id)
        user_tz = user.timezone if user else settings.timezone
        memory_count = len(MemoryRepository(session).list(message.from_user.id))
        now_str = datetime.now(ZoneInfo(user_tz)).strftime("%Y-%m-%d %H:%M:%S %Z")

    status_msg = (
        f"🤖 <b>J.A.R.V.I.S. SYSTEM DIAGNOSTICS</b>\n\n"
        f"🟢 Core Intelligence: Online & Nominal\n"
        f"🛡️ Arc Reactor / Server: 100% Operational\n"
        f"🌍 Chronometer: {user_tz}\n"
        f"🕒 Local Time: {now_str}\n"
        f"🧠 Neural Memories: {memory_count}\n"
        f"⚡ Global News Feeds: 5 Categories Verified\n"
        f"⚡ Multi-LLM Protocol: Active\n\n"
        f"<i>Always at your service, sir.</i>"
    )
    await message.answer(status_msg, parse_mode="HTML")


@fallback_router.message()
async def default_message_handler(message: Message) -> None:
    """Fallback handler only reached when no other command matches."""
    if not message.text:
        return

    text = message.text.strip()

    # If message contains remainder keywords or non-breaking space commands, route directly
    from app.productivity.time_parser import parse_remainder_command
    if text.lower().startswith(("/remainder", "/remind", "/reminder", "remainder", "remind")) or parse_remainder_command(text):
        from app.bot.handlers.productivity import remainder_cmd
        await remainder_cmd(message)
        return

    # If it's an unrecognized slash command, guide user
    if text.startswith("/"):
        await message.answer(
            f"❓ Unrecognized protocol <code>{text.split()[0]}</code>, sir.\n\n"
            "💡 Available Protocols:\n"
            "• <code>Study DSA 16:04</code> — Set reminder directive\n"
            "• <code>ask &lt;query&gt;</code> — Quick intelligence lookup\n"
            "• <code>reminders</code> — View active directives\n"
            "• <code>news</code> — Daily news briefing\n"
            "• <code>settings</code> — Configure core protocols",
            reply_markup=get_main_reply_keyboard(),
            parse_mode="HTML",
        )
        return

    # Freeform natural question without /ask prefix
    answer = await ask_fast_answer(text)
    await message.answer(f"⚡ {answer}", reply_markup=get_main_reply_keyboard())


# Master Router: strictly registers specific command routers first, fallback router last
main_router = Router()
main_router.include_router(base_router)
main_router.include_router(news.router)
main_router.include_router(productivity.router)
main_router.include_router(settings_handler.router)
main_router.include_router(admin.router)
main_router.include_router(fallback_router)
