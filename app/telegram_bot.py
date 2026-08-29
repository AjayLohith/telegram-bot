import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.router import main_router
from app.core.config import settings
from app.scheduler.service import start_scheduler

logger = logging.getLogger(__name__)


async def run_polling() -> None:
    if not settings.telegram_bot_token:
        logger.warning("Telegram polling disabled: TELEGRAM_BOT_TOKEN is required")
        return

    bot = Bot(token=settings.telegram_bot_token)
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)
    dispatcher.include_router(main_router)

    scheduler = start_scheduler(bot)
    logger.info("Starting Telegram bot polling with full productivity and news intelligence...")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        from aiogram.types import BotCommand
        commands = [
            BotCommand(command="remainder", description="Set reminder (e.g. Study DSA 16:04)"),
            BotCommand(command="sheet", description="Google Sheets Assistant & Analytics"),
            BotCommand(command="ask", description="Fast 1-line AI answer"),
            BotCommand(command="news", description="Daily Verified News Digest"),
            BotCommand(command="reminders", description="View & manage active reminders"),
            BotCommand(command="settings", description="Configure timezone & delivery"),
            BotCommand(command="help", description="Commands & Guide"),
        ]
        await bot.set_my_commands(commands)
        await dispatcher.start_polling(bot)

    finally:

        if scheduler is not None:
            scheduler.shutdown(wait=False)
        await bot.session.close()


def start_polling_task() -> asyncio.Task[None] | None:
    if not settings.telegram_polling or not settings.telegram_bot_token:
        return None
    return asyncio.create_task(run_polling(), name="telegram-polling")