import re
from zoneinfo import ZoneInfo, available_timezones
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.formatters import format_settings_overview, format_times_overview
from app.bot.keyboards import get_cancel_keyboard, get_settings_keyboard, get_times_keyboard
from app.bot.states import SettingsTimeState, SettingsTimezoneState
from app.core.database import SessionLocal
from app.database.repositories.user_repo import UserRepository

router = Router()
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@router.message(Command("settings"))
@router.message(F.text.regexp(r"^/settings[\s\u00a0\u2000-\u200f]", mode="search"))
@router.message(F.text.regexp(r"^/settings\b", mode="search"))
@router.message(F.text == "⚙️ Settings")
@router.message(F.text.startswith(("/settings", "settings")))
async def settings_cmd(message: Message) -> None:

    with SessionLocal() as session:
        user, _ = UserRepository(session).get_or_create(message.from_user.id, message.from_user.username)
        text = format_settings_overview(user)
        keyboard = get_settings_keyboard(user)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("times"))
async def times_cmd(message: Message) -> None:
    with SessionLocal() as session:
        user, _ = UserRepository(session).get_or_create(message.from_user.id, message.from_user.username)
        text = format_times_overview(user)
        keyboard = get_times_keyboard(user)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("timezone"))
async def timezone_cmd(message: Message, state: FSMContext) -> None:
    arg = (message.text or "").partition(" ")[2].strip()
    if arg:
        try:
            ZoneInfo(arg)
            with SessionLocal() as session:
                UserRepository(session).update_settings(message.from_user.id, timezone=arg)
            await message.answer(f"✅ Timezone updated to <b>{arg}</b>", parse_mode="HTML")
            return
        except Exception:
            await message.answer(f"❌ Invalid timezone '{arg}'. Example valid: <code>Asia/Kolkata</code>, <code>America/New_York</code>, <code>UTC</code>", parse_mode="HTML")
            return

    await state.set_state(SettingsTimezoneState.waiting_for_timezone)
    await message.answer("🌍 Please enter your timezone (e.g. <code>Asia/Kolkata</code>, <code>UTC</code>, <code>Europe/London</code>):", reply_markup=get_cancel_keyboard(), parse_mode="HTML")


@router.message(SettingsTimezoneState.waiting_for_timezone)
async def process_timezone(message: Message, state: FSMContext) -> None:
    tz_input = (message.text or "").strip()
    try:
        ZoneInfo(tz_input)
        with SessionLocal() as session:
            UserRepository(session).update_settings(message.from_user.id, timezone=tz_input)
        await state.clear()
        await message.answer(f"✅ Timezone updated to <b>{tz_input}</b>!", parse_mode="HTML")
    except Exception:
        await message.answer(f"❌ Invalid timezone '{tz_input}'. Please try again (e.g. <code>Asia/Kolkata</code>):", parse_mode="HTML")


@router.message(Command("settime"))
async def set_time_cmd(message: Message) -> None:
    args = (message.text or "").strip().split()
    if len(args) == 3:
        time_type = args[1].lower()
        time_val = args[2]
        if not _TIME_RE.match(time_val):
            await message.answer("❌ Please provide time in 24h HH:MM format (e.g. 08:30, 14:00).")
            return

        field_map = {
            "morning": "morning_time",
            "news": "news_time",
            "video": "video_time",
            "study": "study_time",
            "exercise": "exercise_time",
            "eod": "eod_time",
        }
        if time_type not in field_map:
            await message.answer(f"❌ Unknown type '{time_type}'. Choose from: morning, news, video, study, exercise, eod.")
            return

        with SessionLocal() as session:
            UserRepository(session).update_settings(message.from_user.id, **{field_map[time_type]: time_val})
        await message.answer(f"✅ <b>{time_type.capitalize()}</b> time set to <b>{time_val}</b>.", parse_mode="HTML")
        return

    await message.answer("Usage: <code>/settime &lt;type&gt; &lt;HH:MM&gt;</code>\nTypes: morning, news, video, study, exercise, eod\nExample: <code>/settime video 10:00</code>", parse_mode="HTML")


@router.message(Command("setnewstime"))
async def set_news_time_cmd(message: Message) -> None:
    args = (message.text or "").strip().split()
    if len(args) == 2 and _TIME_RE.match(args[1]):
        t_val = args[1]
        with SessionLocal() as session:
            UserRepository(session).update_settings(message.from_user.id, news_time=t_val)
        await message.answer(f"✅ Daily News delivery time updated to <b>{t_val}</b>.", parse_mode="HTML")
        return
    await message.answer("Usage: <code>/setnewstime HH:MM</code>\nExample: <code>/setnewstime 08:30</code>", parse_mode="HTML")


@router.callback_query(F.data == "btn_settings")
async def cb_settings(call: CallbackQuery) -> None:
    with SessionLocal() as session:
        user, _ = UserRepository(session).get_or_create(call.from_user.id, call.from_user.username)
        text = format_settings_overview(user)
        keyboard = get_settings_keyboard(user)
    try:
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "set_times")
async def cb_set_times(call: CallbackQuery) -> None:
    with SessionLocal() as session:
        user, _ = UserRepository(session).get_or_create(call.from_user.id, call.from_user.username)
        text = format_times_overview(user)
        keyboard = get_times_keyboard(user)
    try:
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "toggle_notif")
async def cb_toggle_notif(call: CallbackQuery) -> None:
    with SessionLocal() as session:
        user = UserRepository(session).get_by_telegram_id(call.from_user.id)
        if user:
            user.missed_reminders_enabled = not user.missed_reminders_enabled
            session.commit()
            text = format_settings_overview(user)
            keyboard = get_settings_keyboard(user)
            await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "toggle_breaking")
async def cb_toggle_breaking(call: CallbackQuery) -> None:
    with SessionLocal() as session:
        user = UserRepository(session).get_by_telegram_id(call.from_user.id)
        if user:
            user.breaking_news_enabled = not user.breaking_news_enabled
            session.commit()
            text = format_settings_overview(user)
            keyboard = get_settings_keyboard(user)
            await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "toggle_morning_comb")
async def cb_toggle_morning_comb(call: CallbackQuery) -> None:
    with SessionLocal() as session:
        user = UserRepository(session).get_by_telegram_id(call.from_user.id)
        if user:
            user.morning_combined_enabled = not user.morning_combined_enabled
            session.commit()
            text = format_settings_overview(user)
            keyboard = get_settings_keyboard(user)
            await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "set_language")
async def cb_set_language(call: CallbackQuery) -> None:
    with SessionLocal() as session:
        user = UserRepository(session).get_by_telegram_id(call.from_user.id)
        if user:
            # Cycle en -> te -> bilingual -> en
            next_lang = {"en": "te", "te": "bilingual", "bilingual": "en"}.get(user.language, "en")
            user.language = next_lang
            session.commit()
            text = format_settings_overview(user)
            keyboard = get_settings_keyboard(user)
            await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("time_edit:"))
async def cb_time_edit(call: CallbackQuery, state: FSMContext) -> None:
    time_type = call.data.split(":")[1]
    await state.set_state(SettingsTimeState.waiting_for_time)
    await state.update_data(time_type=time_type)
    await call.message.answer(
        f"⏰ Enter new 24-hour time for <b>{time_type.capitalize()}</b> (e.g. <code>08:30</code> or <code>14:00</code>):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(SettingsTimeState.waiting_for_time)
async def process_setting_time(message: Message, state: FSMContext) -> None:
    time_val = (message.text or "").strip()
    if not _TIME_RE.match(time_val):
        await message.answer("❌ Invalid format. Please enter HH:MM in 24h format (e.g. 08:30 or 18:00):")
        return

    data = await state.get_data()
    time_type = data["time_type"]
    field_map = {
        "morning": "morning_time",
        "news": "news_time",
        "video": "video_time",
        "study": "study_time",
        "exercise": "exercise_time",
        "eod": "eod_time",
    }
    field = field_map.get(time_type, f"{time_type}_time")

    with SessionLocal() as session:
        user = UserRepository(session).update_settings(message.from_user.id, **{field: time_val})
        text = format_times_overview(user)
        keyboard = get_times_keyboard(user)

    await state.clear()
    await message.answer(f"✅ <b>{time_type.capitalize()}</b> time updated to <b>{time_val}</b>!\n\n{text}", reply_markup=keyboard, parse_mode="HTML")
