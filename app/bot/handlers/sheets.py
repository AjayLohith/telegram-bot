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
            InlineKeyboardButton(text="📊 Overview / Summary", callback_data="sheet_summary"),
            InlineKeyboardButton(text="🔄 Refresh Data", callback_data="sheet_refresh"),
        ],
        [
            InlineKeyboardButton(text="🏆 Top Products / Items", callback_data="sheet_top"),
            InlineKeyboardButton(text="📈 Total Sales / Metrics", callback_data="sheet_totals"),
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

    # If no spreadsheet configured
    if not settings.google_spreadsheet_id:
        await message.answer(
            "📊 <b>Google Sheets Assistant</b>\n\n"
            "⚠️ No Google Spreadsheet ID is configured in the environment.\n"
            "To connect your sheet, add <code>GOOGLE_SPREADSHEET_ID=&lt;your-sheet-id&gt;</code> to your <code>.env</code> file.",
            parse_mode="HTML",
        )
        return

    # If empty command, provide overview + interactive buttons
    if not query:
        status_msg = await message.answer("🔄 Connecting to Google Sheet...", parse_mode="HTML")
        overview = await sheet_service.get_overview()
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.answer(overview, reply_markup=get_sheets_inline_keyboard(), parse_mode="HTML")
        return

    status_msg = await message.answer("🔍 Analyzing Google Sheet data...", parse_mode="HTML")
    answer = await sheet_service.answer_question(query)
    try:
        await status_msg.delete()
    except Exception:
        pass
    await message.answer(answer, parse_mode="HTML")


@router.message(F.text == "📊 Sheet Data")
async def sheet_button(message: Message) -> None:
    if not settings.google_spreadsheet_id:
        await message.answer(
            "📊 <b>Google Sheets Assistant</b>\n\n"
            "⚠️ No Google Spreadsheet is configured yet in <code>.env</code>.\n"
            "Please configure <code>GOOGLE_SPREADSHEET_ID</code>.",
            parse_mode="HTML",
        )
        return

    status_msg = await message.answer("🔄 Loading Google Sheet intelligence...", parse_mode="HTML")
    overview = await sheet_service.get_overview()
    try:
        await status_msg.delete()
    except Exception:
        pass
    await message.answer(overview, reply_markup=get_sheets_inline_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "sheet_summary")
async def cb_sheet_summary(callback: CallbackQuery) -> None:
    await callback.answer("Loading sheet overview...")
    overview = await sheet_service.get_overview()
    if callback.message:
        await callback.message.answer(overview, reply_markup=get_sheets_inline_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "sheet_refresh")
async def cb_sheet_refresh(callback: CallbackQuery) -> None:
    await callback.answer("Refreshing data...")
    res = await sheet_service.refresh()
    if callback.message:
        await callback.message.answer(res, reply_markup=get_sheets_inline_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "sheet_top")
async def cb_sheet_top(callback: CallbackQuery) -> None:
    await callback.answer("Computing top items...")
    answer = await sheet_service.answer_question("Show top 5 entries by highest metrics")
    if callback.message:
        await callback.message.answer(answer, parse_mode="HTML")


@router.callback_query(F.data == "sheet_totals")
async def cb_sheet_totals(callback: CallbackQuery) -> None:
    await callback.answer("Calculating totals...")
    answer = await sheet_service.answer_question("What are the total sales and key metrics?")
    if callback.message:
        await callback.message.answer(answer, parse_mode="HTML")
