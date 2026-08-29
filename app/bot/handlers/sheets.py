import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.config import settings
from app.sheets.service import SheetAIService

logger = logging.getLogger(__name__)

router = Router()
sheet_service = SheetAIService()


def get_sheets_inline_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🏆 Winner Today", callback_data="sheet_winner"),
            InlineKeyboardButton(text="👑 Leaderboard", callback_data="sheet_leaderboard"),
        ],
        [
            InlineKeyboardButton(text="🔥 Habit Streaks", callback_data="sheet_streaks"),
            InlineKeyboardButton(text="📅 Daily Log", callback_data="sheet_daily"),
        ],
        [
            InlineKeyboardButton(text="🔄 Refresh Data", callback_data="sheet_refresh"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("sheet"))
@router.message(Command("sheets"))
@router.message(F.text.startswith(("/sheet", "/sheets", "sheet ", "sheets ")))
async def sheet_command(message: Message) -> None:
    raw = message.text or ""
    
    # Extract query if present
    query = ""
    for prefix in ("/sheets", "/sheet", "sheets ", "sheet "):
        if raw.lower().startswith(prefix):
            query = raw[len(prefix):].strip()
            break

    # If empty command, provide overview + interactive buttons
    if not query:
        status_msg = await message.answer("🔄 Connecting to Competition Tracker...", parse_mode="HTML")
        overview = await sheet_service.get_overview()
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.answer(overview, reply_markup=get_sheets_inline_keyboard(), parse_mode="HTML")
        return

    status_msg = await message.answer("🔍 Analyzing competition data...", parse_mode="HTML")
    answer = await sheet_service.answer_question(query)
    try:
        await status_msg.delete()
    except Exception:
        pass
    await message.answer(answer, parse_mode="HTML")


@router.message(F.text == "📊 Sheet Data")
async def sheet_button(message: Message) -> None:
    status_msg = await message.answer("🔄 Loading Competition Intelligence...", parse_mode="HTML")
    overview = await sheet_service.get_overview()
    try:
        await status_msg.delete()
    except Exception:
        pass
    await message.answer(overview, reply_markup=get_sheets_inline_keyboard(), parse_mode="HTML")


async def _safe_edit_or_answer(callback: CallbackQuery, text: str) -> None:
    if not callback.message:
        return
    try:
        await callback.message.edit_text(text, reply_markup=get_sheets_inline_keyboard(), parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "sheet_winner")
async def cb_sheet_winner(callback: CallbackQuery) -> None:
    await callback.answer("Loading winner data...")
    answer = await sheet_service.answer_question("who is the winner today")
    await _safe_edit_or_answer(callback, answer)


@router.callback_query(F.data == "sheet_leaderboard")
async def cb_sheet_leaderboard(callback: CallbackQuery) -> None:
    await callback.answer("Loading leaderboard...")
    answer = await sheet_service.answer_question("leaderboard standings")
    await _safe_edit_or_answer(callback, answer)


@router.callback_query(F.data == "sheet_streaks")
async def cb_sheet_streaks(callback: CallbackQuery) -> None:
    await callback.answer("Loading habit streaks...")
    answer = await sheet_service.answer_question("streaks")
    await _safe_edit_or_answer(callback, answer)


@router.callback_query(F.data == "sheet_daily")
async def cb_sheet_daily(callback: CallbackQuery) -> None:
    await callback.answer("Loading daily log...")
    answer = await sheet_service.answer_question("daily log")
    await _safe_edit_or_answer(callback, answer)


@router.callback_query(F.data == "sheet_summary")
async def cb_sheet_summary(callback: CallbackQuery) -> None:
    await callback.answer("Loading overview...")
    overview = await sheet_service.get_overview()
    await _safe_edit_or_answer(callback, overview)


@router.callback_query(F.data == "sheet_refresh")
async def cb_sheet_refresh(callback: CallbackQuery) -> None:
    await callback.answer("Refreshing live data...")
    res = await sheet_service.refresh()
    await _safe_edit_or_answer(callback, res)
