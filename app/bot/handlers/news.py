from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.formatters import format_sources_overview
from app.core.database import SessionLocal
from app.database.repositories.user_repo import UserRepository
from app.news.digest import build_category_digest, build_compact_digest, build_full_daily_digest
from app.news.service import NewsService

router = Router()


def _get_user_lang(telegram_id: int) -> str:
    with SessionLocal() as session:
        user = UserRepository(session).get_by_telegram_id(telegram_id)
        return user.language if user else "en"


@router.message(Command("testnews"))
async def test_news_cmd(message: Message) -> None:
    """Instantly delivers the complete 07:00 AM news briefing as a test push notification."""
    lang = _get_user_lang(message.from_user.id)
    status_msg = await message.answer("🔄 Generating test 07:00 AM news briefing, sir...")
    with SessionLocal() as session:
        sections = await build_full_daily_digest(session, language=lang)
    await status_msg.delete()
    for section in sections:
        if section.strip():
            await message.answer(section, parse_mode="HTML", disable_web_page_preview=True, disable_notification=False)


@router.message(Command("news"))
@router.message(F.text.regexp(r"^/news[\s\u00a0\u2000-\u200f]", mode="search"))
@router.message(F.text.regexp(r"^/news\b", mode="search"))
@router.message(F.text == "📰 Today's News")
@router.message(F.text.startswith(("/news", "news")))
async def news_command(message: Message) -> None:


    args = (message.text or "").strip().split()
    lang = _get_user_lang(message.from_user.id)

    # Check if compact digest requested (e.g. /news 5)
    if len(args) > 1 and args[1] == "5":
        status_msg = await message.answer("🔄 Fetching top 5 verified news stories...")
        with SessionLocal() as session:
            compact = await build_compact_digest(session, total=5, language=lang)
        await status_msg.delete()
        await message.answer(compact, parse_mode="HTML")
        return

    status_msg = await message.answer("🔄 Preparing your 25-item Daily Intelligence Digest...")
    with SessionLocal() as session:
        sections = await build_full_daily_digest(session, language=lang)

    await status_msg.delete()
    for section in sections:
        if section.strip():
            await message.answer(section, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data == "btn_news")
async def cb_news(call: CallbackQuery) -> None:
    lang = _get_user_lang(call.from_user.id)
    await call.answer("Fetching today's digest...")
    status_msg = await call.message.answer("🔄 Preparing your 25-item Daily Intelligence Digest...")
    with SessionLocal() as session:
        sections = await build_full_daily_digest(session, language=lang)

    await status_msg.delete()
    for section in sections:
        if section.strip():
            await call.message.answer(section, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("ai"))
async def ai_news_cmd(message: Message) -> None:
    lang = _get_user_lang(message.from_user.id)
    status_msg = await message.answer("🔄 Fetching 5 verified AI developments...")
    with SessionLocal() as session:
        text = await build_category_digest(session, "ai", limit=5, language=lang)
    await status_msg.delete()
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("world"))
async def world_news_cmd(message: Message) -> None:
    lang = _get_user_lang(message.from_user.id)
    status_msg = await message.answer("🔄 Fetching 5 Geography & World developments...")
    with SessionLocal() as session:
        text = await build_category_digest(session, "world", limit=5, language=lang)
    await status_msg.delete()
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("anime"))
async def anime_news_cmd(message: Message) -> None:
    lang = _get_user_lang(message.from_user.id)
    status_msg = await message.answer("🔄 Fetching 5 verified Anime developments...")
    with SessionLocal() as session:
        text = await build_category_digest(session, "anime", limit=5, language=lang)
    await status_msg.delete()
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("telugu"))
async def telugu_news_cmd(message: Message) -> None:
    lang = _get_user_lang(message.from_user.id)
    status_msg = await message.answer("🔄 Fetching 5 verified Telugu & AP/TS developments...")
    with SessionLocal() as session:
        text = await build_category_digest(session, "telugu", limit=5, language=lang)
    await status_msg.delete()
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("india"))
async def india_news_cmd(message: Message) -> None:
    lang = _get_user_lang(message.from_user.id)
    status_msg = await message.answer("🔄 Fetching 5 verified India developments...")
    with SessionLocal() as session:
        text = await build_category_digest(session, "india", limit=5, language=lang)
    await status_msg.delete()
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("sources"))
async def sources_cmd(message: Message) -> None:
    with SessionLocal() as session:
        service = NewsService(session)
        summary = service.get_sources_summary()
    text = format_sources_overview(summary)
    await message.answer(text, parse_mode="HTML")
