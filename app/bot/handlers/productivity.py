from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.formatters import format_daily_summary, format_streak_stats, format_tasks_overview
from app.bot.keyboards import get_cancel_keyboard, get_tasks_inline_keyboard
from app.bot.states import AddTaskState, DailyRemarksState, EditTaskState, TaskRemarksState, TaskUpdateState
from app.core.config import settings
from app.core.database import SessionLocal
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.user_repo import UserRepository
from app.productivity.service import ProductivityService

router = Router()


def _get_user_and_today(telegram_id: int, username: str | None = None):
    with SessionLocal() as session:
        user_repo = UserRepository(session)
        user, _ = user_repo.get_or_create(telegram_id, username)
        tz_str = user.timezone or settings.timezone
        user_tz = ZoneInfo(tz_str)
        today = datetime.now(user_tz).date()
        user_id = user.id
    return user_id, today, tz_str


@router.message(Command("tasks"))
@router.message(Command("today"))
@router.message(F.text == "📋 Today's Tasks")
async def show_tasks(message: Message) -> None:
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)
    with SessionLocal() as session:
        service = ProductivityService(session)
        progress = service.get_daily_progress(user_id, today)
        keyboard = get_tasks_inline_keyboard(progress.tasks)
        text = format_tasks_overview(progress)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("progress"))
@router.message(F.text == "📊 Progress")
async def show_progress(message: Message) -> None:
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)
    with SessionLocal() as session:
        service = ProductivityService(session)
        progress = service.get_daily_progress(user_id, today)
        summary = format_daily_summary(progress)
    await message.answer(summary, parse_mode="HTML")


@router.message(Command("streak"))
@router.message(F.text == "🔥 Streak")
async def show_streak(message: Message) -> None:
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)
    with SessionLocal() as session:
        service = ProductivityService(session)
        stats = service.get_streak_stats(user_id, today)
        text = format_streak_stats(stats)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("remarks"))
@router.message(F.text == "📝 Add Remarks")
async def add_remarks_cmd(message: Message, state: FSMContext) -> None:
    content = (message.text or "").partition(" ")[2].strip()
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)
    if content and message.text != "📝 Add Remarks":
        with SessionLocal() as session:
            service = ProductivityService(session)
            service.save_eod_summary(user_id, today, remarks=content)
        await message.answer(f"✅ Remarks saved for today: <i>{content}</i>", parse_mode="HTML")
        return

    await state.set_state(DailyRemarksState.waiting_for_remarks)
    await message.answer(
        "📝 Please reply with your remarks/reflections for today:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(DailyRemarksState.waiting_for_remarks)
async def process_daily_remarks(message: Message, state: FSMContext) -> None:
    remarks_text = message.text or ""
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)
    with SessionLocal() as session:
        service = ProductivityService(session)
        service.save_eod_summary(user_id, today, remarks=remarks_text)
    await state.clear()
    await message.answer(f"✅ <b>Remarks saved!</b>\n\n\"{remarks_text}\"", parse_mode="HTML")


@router.callback_query(F.data == "btn_progress")
async def cb_progress(call: CallbackQuery) -> None:
    user_id, today, _ = _get_user_and_today(call.from_user.id, call.from_user.username)
    with SessionLocal() as session:
        service = ProductivityService(session)
        progress = service.get_daily_progress(user_id, today)
        summary = format_daily_summary(progress)
    await call.message.answer(summary, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "btn_streak")
async def cb_streak(call: CallbackQuery) -> None:
    user_id, today, _ = _get_user_and_today(call.from_user.id, call.from_user.username)
    with SessionLocal() as session:
        service = ProductivityService(session)
        stats = service.get_streak_stats(user_id, today)
        text = format_streak_stats(stats)
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "btn_tasks")
async def cb_tasks(call: CallbackQuery) -> None:
    user_id, today, _ = _get_user_and_today(call.from_user.id, call.from_user.username)
    with SessionLocal() as session:
        service = ProductivityService(session)
        progress = service.get_daily_progress(user_id, today)
        keyboard = get_tasks_inline_keyboard(progress.tasks)
        text = format_tasks_overview(progress)
    try:
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("task_skip:"))
async def cb_task_skip(call: CallbackQuery) -> None:
    task_id = int(call.data.split(":")[1])
    user_id, today, _ = _get_user_and_today(call.from_user.id, call.from_user.username)
    with SessionLocal() as session:
        service = ProductivityService(session)
        t = service.skip_task(user_id, task_id, today)
        progress = service.get_daily_progress(user_id, today)
        keyboard = get_tasks_inline_keyboard(progress.tasks)
        text = format_tasks_overview(progress)
    await call.answer(f"Skipped {t.name}")
    try:
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("task_done:"))
async def cb_task_done(call: CallbackQuery, state: FSMContext) -> None:
    task_id = int(call.data.split(":")[1])
    user_id, today, _ = _get_user_and_today(call.from_user.id, call.from_user.username)

    with SessionLocal() as session:
        task_repo = TaskRepository(session)
        task = task_repo.get_task_by_id(task_id)
        if not task:
            await call.answer("Task not found.")
            return

        if task.task_type == "video":
            # Prompt for video details or mark directly
            await state.set_state(TaskUpdateState.waiting_for_details)
            await state.update_data(task_id=task_id, task_type="video", target_val=1.0)
            await call.message.answer(
                "🎥 <b>Video Completed!</b>\n\nPlease enter the Video Title (or send 'skip' to save without details):",
                reply_markup=get_cancel_keyboard(),
                parse_mode="HTML",
            )
            await call.answer()
            return

        elif task.task_type in {"study", "exercise"}:
            await state.set_state(TaskUpdateState.waiting_for_value)
            await state.update_data(task_id=task_id, task_type=task.task_type, target_val=task.target_value, unit=task.target_unit)
            unit_label = task.target_unit
            await call.message.answer(
                f"⏱ Enter actual <b>{task.name}</b> {unit_label} (Target: {task.target_value:g} {unit_label}):",
                reply_markup=get_cancel_keyboard(),
                parse_mode="HTML",
            )
            await call.answer()
            return

        else:
            # Custom task: complete directly
            service = ProductivityService(session)
            service.complete_task(user_id, task_id, today)
            progress = service.get_daily_progress(user_id, today)
            keyboard = get_tasks_inline_keyboard(progress.tasks)
            text = format_tasks_overview(progress)

    await call.answer(f"✅ Completed {task.name}")
    try:
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("task_update:"))
async def cb_task_update(call: CallbackQuery, state: FSMContext) -> None:
    task_id = int(call.data.split(":")[1])
    with SessionLocal() as session:
        task_repo = TaskRepository(session)
        task = task_repo.get_task_by_id(task_id)
        if not task:
            await call.answer("Task not found.")
            return

        await state.set_state(TaskUpdateState.waiting_for_value)
        await state.update_data(task_id=task_id, task_type=task.task_type, target_val=task.target_value, unit=task.target_unit)
        unit_label = task.target_unit

    await call.message.answer(
        f"⏱ Enter actual {unit_label} completed for <b>{task.name}</b> (Target: {task.target_value:g} {unit_label}):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(TaskUpdateState.waiting_for_value)
async def process_task_value(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        val = float(text)
        if val < 0:
            raise ValueError()
    except ValueError:
        await message.answer("Please enter a valid positive number (e.g. 3 or 2.5 or 45):")
        return

    data = await state.get_data()
    task_id = data["task_id"]
    task_type = data.get("task_type", "custom")
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)

    if task_type == "study":
        await state.update_data(actual_value=val)
        await state.set_state(TaskUpdateState.waiting_for_details)
        await message.answer("📚 What subject/topic did you study? (or send 'skip'):", reply_markup=get_cancel_keyboard())
        return
    elif task_type == "exercise":
        await state.update_data(actual_value=val)
        await state.set_state(TaskUpdateState.waiting_for_details)
        await message.answer("🏃 What exercise did you do? (e.g. Running, Gym, Yoga, Walking — or send 'skip'):", reply_markup=get_cancel_keyboard())
        return

    with SessionLocal() as session:
        service = ProductivityService(session)
        service.update_task_progress(user_id, task_id, today, actual_value=val)
        progress = service.get_daily_progress(user_id, today)
        keyboard = get_tasks_inline_keyboard(progress.tasks)
        overview = format_tasks_overview(progress)

    await state.clear()
    await message.answer(f"✅ Progress updated!\n\n{overview}", reply_markup=keyboard, parse_mode="HTML")


@router.message(TaskUpdateState.waiting_for_details)
async def process_task_details(message: Message, state: FSMContext) -> None:
    detail_text = (message.text or "").strip()
    data = await state.get_data()
    task_id = data["task_id"]
    task_type = data.get("task_type", "custom")
    actual_val = data.get("actual_value", 1.0)
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)

    details = {}
    if detail_text.lower() != "skip":
        if task_type == "video":
            details["video_title"] = detail_text
        elif task_type == "study":
            details["subject"] = detail_text
        elif task_type == "exercise":
            details["exercise_type"] = detail_text

    with SessionLocal() as session:
        service = ProductivityService(session)
        service.complete_task(user_id, task_id, today, actual_value=actual_val, details=details)
        progress = service.get_daily_progress(user_id, today)
        keyboard = get_tasks_inline_keyboard(progress.tasks)
        overview = format_tasks_overview(progress)

    await state.clear()
    await message.answer(f"✅ Task updated!\n\n{overview}", reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "cancel_action")
async def cb_cancel_action(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("❌ Action cancelled.")
    await call.answer()


# Task Management Commands: /addtask, /removetask, /edittask
@router.message(Command("addtask"))
async def add_task_cmd(message: Message, state: FSMContext) -> None:
    await state.set_state(AddTaskState.waiting_for_name)
    await message.answer("📌 Enter the name for the new task:", reply_markup=get_cancel_keyboard())


@router.message(AddTaskState.waiting_for_name)
async def add_task_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    await state.update_data(name=name)
    await state.set_state(AddTaskState.waiting_for_target)
    await message.answer("🎯 Enter the target number (e.g. 1 or 30 or 4):", reply_markup=get_cancel_keyboard())


@router.message(AddTaskState.waiting_for_target)
async def add_task_target(message: Message, state: FSMContext) -> None:
    try:
        val = float(message.text.strip())
        if val <= 0:
            raise ValueError()
    except Exception:
        await message.answer("Please enter a valid positive number:")
        return
    await state.update_data(target_val=val)
    await state.set_state(AddTaskState.waiting_for_unit)
    await message.answer("📏 Enter the unit (e.g. hours, minutes, count, done):", reply_markup=get_cancel_keyboard())


@router.message(AddTaskState.waiting_for_unit)
async def add_task_unit(message: Message, state: FSMContext) -> None:
    unit = (message.text or "").strip().lower()
    await state.update_data(unit=unit)
    await state.set_state(AddTaskState.waiting_for_points)
    await message.answer("⭐ Enter points for this task (e.g. 20):", reply_markup=get_cancel_keyboard())


@router.message(AddTaskState.waiting_for_points)
async def add_task_points(message: Message, state: FSMContext) -> None:
    try:
        pts = float(message.text.strip())
    except Exception:
        await message.answer("Please enter a valid number for points:")
        return

    data = await state.get_data()
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)

    with SessionLocal() as session:
        task_repo = TaskRepository(session)
        task = task_repo.add_task(
            user_id=user_id,
            name=data["name"],
            task_type="custom",
            target_value=data["target_val"],
            target_unit=data["unit"],
            points=pts,
            reminder_time="10:00",
        )
    await state.clear()
    await message.answer(f"✅ Added task <b>{task.name}</b> ({task.points:g} pts)!", parse_mode="HTML")


@router.message(Command("removetask"))
async def remove_task_cmd(message: Message) -> None:
    user_id, today, _ = _get_user_and_today(message.from_user.id, message.from_user.username)
    with SessionLocal() as session:
        task_repo = TaskRepository(session)
        tasks = task_repo.get_user_tasks(user_id, active_only=True)
        if not tasks:
            await message.answer("No active tasks to remove.")
            return
        lines = ["Select task to remove with <code>/removetask &lt;ID&gt;</code>:\n"]
        for t in tasks:
            lines.append(f"ID {t.id}: {t.name} ({t.points:g} pts)")
    
    arg = (message.text or "").partition(" ")[2].strip()
    if arg.isdigit():
        task_id = int(arg)
        with SessionLocal() as session:
            task_repo = TaskRepository(session)
            deleted = task_repo.delete_task(task_id)
        if deleted:
            await message.answer(f"✅ Task ID {task_id} removed.")
        else:
            await message.answer(f"❌ Task ID {task_id} not found.")
        return

    await message.answer("\n".join(lines), parse_mode="HTML")


# ==========================================
# /REMAINDER COMMANDS SUITE (Master Prompt V2)
# ==========================================

from app.database.repositories.reminder_repo import ReminderRepository
from app.productivity.reminder_ai import format_reminder_message, generate_reminder_focus
from app.productivity.time_parser import parse_remainder_command, parse_time_string


@router.message(Command("remainder", "remind", "reminder"))
@router.message(F.text.regexp(r"^/(?:remainder|remind|reminder)[\s\u00a0\u2000-\u200f]", mode="search"))
@router.message(F.text.regexp(r"^/(?:remainder|remind|reminder)\b", mode="search"))
@router.message(F.text.startswith(("/remainder", "/remind", "/reminder", "remainder ", "remind ")))
async def remainder_cmd(message: Message) -> None:

    text = message.text or ""
    parsed = parse_remainder_command(text)
    if not parsed:
        parts = text.strip().split()
        if len(parts) <= 1:
            await message.answer("❌ Please provide a task and time.\n\nExample:\n<code>/remainder Study DSA 8:30 PM</code>\n<code>/remainder Go for exercise 6:00 PM</code>", parse_mode="HTML")
            return
        await message.answer("❌ Invalid time format.\n\nPlease provide time in 12-hour or 24-hour format (e.g. <code>8:30 PM</code>, <code>7 AM</code>, <code>2:00 PM</code>, <code>19:30</code>).\n\nExample:\n<code>/remainder Study DSA 8:30 PM</code>", parse_mode="HTML")
        return

    task_name, time_24h, display_12h = parsed
    with SessionLocal() as session:
        user_repo = UserRepository(session)
        user, _ = user_repo.get_or_create(message.from_user.id, message.from_user.username)
        tz_name = user.timezone or settings.timezone
        
        rem_repo = ReminderRepository(session)
        reminder = rem_repo.add_reminder(
            telegram_user_id=message.from_user.id,
            task_name=task_name,
            reminder_time_24h=time_24h,
            display_time_12h=display_12h,
            timezone=tz_name,
            recurrence="DAILY",
        )

    response_text = (
        f"✅ <b>Reminder created</b>\n\n"
        f"<b>Task:</b> {reminder.task_name}\n"
        f"<b>Time:</b> {reminder.display_time} {tz_name}\n"
        f"<b>Status:</b> Active\n"
        f"<b>ID:</b> {reminder.id}"
    )
    await message.answer(response_text, parse_mode="HTML")


@router.message(Command("reminders"))
@router.message(F.text == "⏰ My Reminders")
@router.callback_query(F.data == "btn_reminders")
async def list_reminders_cmd(event: Message | CallbackQuery) -> None:
    from app.bot.keyboards import get_reminders_list_keyboard
    user_id = event.from_user.id
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        reminders = rem_repo.list_user_reminders(user_id)

    if not reminders:
        msg = "ℹ️ <b>You have no active reminders yet.</b>\n\nCreate a reminder by sending:\n<code>/remainder Study DSA 8:30 PM</code>\n<code>/remainder Go for exercise 6:00 PM</code>"
        if isinstance(event, CallbackQuery):
            await event.message.answer(msg, parse_mode="HTML")
            await event.answer()
        else:
            await event.answer(msg, parse_mode="HTML")
        return

    text = f"⏰ <b>YOUR SCHEDULED REMINDERS ({len(reminders)})</b>\n\nTap below to Pause, Test, or Delete any reminder:"
    kb = get_reminders_list_keyboard(reminders)

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "➕ Add Reminder")
@router.callback_query(F.data == "btn_add_reminder")
async def add_reminder_prompt(event: Message | CallbackQuery) -> None:
    text = (
        "➕ <b>HOW TO CREATE A REMINDER</b>\n\n"
        "Simply type <code>/remainder &lt;task&gt; &lt;time&gt;</code> in the chat.\n\n"
        "<b>Examples:</b>\n"
        "• <code>/remainder Study DSA 8:30 PM</code>\n"
        "• <code>/remainder Go for exercise 6:00 PM</code>\n"
        "• <code>/remainder Watch AI lecture 10:30 AM</code>\n"
        "• <code>/remainder Read book 7 AM</code>\n\n"
        "<i>Accepts standard 12-hour (e.g. 8:30 PM) or 24-hour (19:30) times.</i>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("rem_toggle:"))
async def cb_rem_toggle(call: CallbackQuery) -> None:
    from app.bot.keyboards import get_reminders_list_keyboard
    rem_id = int(call.data.split(":")[1])
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        rem = rem_repo.get_reminder(rem_id, call.from_user.id)
        if not rem:
            await call.answer("Reminder not found.", show_alert=True)
            return
        new_active = not rem.active
        rem_repo.set_active_status(rem_id, call.from_user.id, active=new_active)
        reminders = rem_repo.list_user_reminders(call.from_user.id)

    status_str = "Resumed" if new_active else "Paused"
    await call.answer(f"Reminder #{rem_id} {status_str}")
    kb = get_reminders_list_keyboard(reminders)
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data.startswith("rem_done:"))
async def cb_rem_done(call: CallbackQuery) -> None:
    rem_id = int(call.data.split(":")[1])
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        reminder = rem_repo.get_reminder(rem_id, call.from_user.id)
        if not reminder:
            await call.answer("Reminder not found.", show_alert=True)
            return
        task_name = reminder.task_name

    await call.answer(f"🎉 Completed: {task_name}!", show_alert=False)
    name = call.from_user.first_name or "Champion"
    msg = (
        f"🎉 <b>Awesome job, {name}!</b>\n\n"
        f"✅ <b>{task_name}</b> marked as completed for today!\n\n"
        f"🔥 Keep the momentum going. Consistency is key!"
    )
    await call.message.answer(msg, parse_mode="HTML")


@router.callback_query(F.data.startswith("rem_test:"))
async def cb_rem_test(call: CallbackQuery) -> None:
    rem_id = int(call.data.split(":")[1])
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        reminder = rem_repo.get_reminder(rem_id, call.from_user.id)

    if not reminder:
        await call.answer("Reminder not found.", show_alert=True)
        return

    await call.answer("Sending test reminder...")
    bullets = await generate_reminder_focus(reminder.task_name)
    rem_msg = format_reminder_message(
        task_name=reminder.task_name,
        display_time=reminder.display_time or reminder.reminder_time,
        tz_name=reminder.timezone,
        focus_bullets=bullets,
    )
    await call.message.answer(f"🧪 <b>[Test Reminder Trigger]</b>\n\n{rem_msg}", parse_mode="HTML")



@router.callback_query(F.data.startswith("rem_del:"))
async def cb_rem_del(call: CallbackQuery) -> None:
    from app.bot.keyboards import get_reminders_list_keyboard
    rem_id = int(call.data.split(":")[1])
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        deleted = rem_repo.delete_reminder(rem_id, call.from_user.id)
        reminders = rem_repo.list_user_reminders(call.from_user.id)

    if deleted:
        await call.answer(f"Reminder #{rem_id} deleted.")
        kb = get_reminders_list_keyboard(reminders)
        try:
            await call.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass
    else:
        await call.answer("Reminder not found.", show_alert=True)



@router.message(Command("deleteremainder"))
@router.message(Command("deletereminder"))
async def delete_reminder_cmd(message: Message) -> None:
    arg = (message.text or "").partition(" ")[2].strip()
    if not arg.isdigit():
        await message.answer("Usage: <code>/deleteremainder &lt;id&gt;</code>\nExample: <code>/deleteremainder 1</code>", parse_mode="HTML")
        return

    rem_id = int(arg)
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        deleted = rem_repo.delete_reminder(rem_id, message.from_user.id)

    if deleted:
        await message.answer(f"✅ Reminder #{rem_id} deleted.")
    else:
        await message.answer(f"❌ Reminder #{rem_id} not found.")


@router.message(Command("editremainder"))
@router.message(Command("editreminder"))
async def edit_reminder_cmd(message: Message) -> None:
    parts = (message.text or "").strip().split()
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Usage: <code>/editremainder &lt;id&gt; &lt;task&gt; &lt;time&gt;</code>\nExample: <code>/editremainder 1 Study DSA 9:00 PM</code>", parse_mode="HTML")
        return

    rem_id = int(parts[1])
    rest_text = " ".join(parts[2:])
    parsed = parse_remainder_command(rest_text)
    if not parsed:
        await message.answer("❌ Invalid format. Please provide task and time.\nExample: <code>/editremainder 1 Study DSA 9:00 PM</code>", parse_mode="HTML")
        return

    task_name, time_24h, display_12h = parsed
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        updated = rem_repo.update_reminder(
            reminder_id=rem_id,
            telegram_user_id=message.from_user.id,
            task_name=task_name,
            reminder_time=time_24h,
            display_time=display_12h,
        )

    if updated:
        await message.answer(f"✅ Reminder #{rem_id} updated:\n<b>Task:</b> {updated.task_name}\n<b>Time:</b> {updated.display_time}", parse_mode="HTML")
    else:
        await message.answer(f"❌ Reminder #{rem_id} not found.")


@router.message(Command("pause"))
async def pause_reminder_cmd(message: Message) -> None:
    arg = (message.text or "").partition(" ")[2].strip()
    if not arg.isdigit():
        await message.answer("Usage: <code>/pause &lt;id&gt;</code>\nExample: <code>/pause 1</code>", parse_mode="HTML")
        return

    rem_id = int(arg)
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        updated = rem_repo.set_active_status(rem_id, message.from_user.id, active=False)

    if updated:
        await message.answer(f"⏸ Reminder #{rem_id} (<b>{updated.task_name}</b>) paused.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Reminder #{rem_id} not found.")


@router.message(Command("resume"))
async def resume_reminder_cmd(message: Message) -> None:
    arg = (message.text or "").partition(" ")[2].strip()
    if not arg.isdigit():
        await message.answer("Usage: <code>/resume &lt;id&gt;</code>\nExample: <code>/resume 1</code>", parse_mode="HTML")
        return

    rem_id = int(arg)
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        updated = rem_repo.set_active_status(rem_id, message.from_user.id, active=True)

    if updated:
        await message.answer(f"▶️ Reminder #{rem_id} (<b>{updated.task_name}</b>) resumed.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Reminder #{rem_id} not found.")


@router.message(Command("testreminder"))
async def test_reminder_cmd(message: Message) -> None:
    arg = (message.text or "").partition(" ")[2].strip()
    with SessionLocal() as session:
        rem_repo = ReminderRepository(session)
        if arg.isdigit():
            reminder = rem_repo.get_reminder(int(arg), message.from_user.id)
        else:
            reminders = rem_repo.list_user_reminders(message.from_user.id)
            reminder = reminders[0] if reminders else None

    if not reminder:
        await message.answer("❌ No reminder found to test. Create one with /remainder first.")
        return

    bullets = await generate_reminder_focus(reminder.task_name)
    rem_msg = format_reminder_message(
        task_name=reminder.task_name,
        display_time=reminder.display_time or reminder.reminder_time,
        tz_name=reminder.timezone,
        focus_bullets=bullets,
    )
    await message.answer(f"🧪 <b>[Test Reminder Trigger]</b>\n\n{rem_msg}", parse_mode="HTML")

