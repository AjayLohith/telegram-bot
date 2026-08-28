from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.database.models import User


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📰 Today's News"), KeyboardButton(text="⏰ My Reminders")],
            [KeyboardButton(text="➕ Add Reminder"), KeyboardButton(text="❓ Ask AI")],
            [KeyboardButton(text="⚙️ Settings")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )



def get_clean_dashboard_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📰 Read Today's News", callback_data="btn_news"),
            InlineKeyboardButton(text="⏰ My Reminders", callback_data="btn_reminders"),
        ],
        [
            InlineKeyboardButton(text="➕ Add New Reminder", callback_data="btn_add_reminder"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="btn_settings"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tasks_inline_keyboard(tasks=None) -> InlineKeyboardMarkup:
    return get_clean_dashboard_keyboard()



def get_reminder_delivery_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Mark as Done", callback_data=f"rem_done:{reminder_id}"),
                InlineKeyboardButton(text="⏰ Reminders", callback_data="btn_reminders"),
            ]
        ]
    )


def get_reminders_list_keyboard(reminders: list) -> InlineKeyboardMarkup:
    buttons = []
    for r in reminders:
        status_icon = "🟢" if r.active else "⏸"
        label = f"{status_icon} {r.task_name} ({r.display_time or r.reminder_time})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"rem_info:{r.id}")])
        buttons.append([
            InlineKeyboardButton(text="⚡ Test", callback_data=f"rem_test:{r.id}"),
            InlineKeyboardButton(text="✅ Done", callback_data=f"rem_done:{r.id}"),
            InlineKeyboardButton(text="⏸ Pause" if r.active else "▶️ Resume", callback_data=f"rem_toggle:{r.id}"),
            InlineKeyboardButton(text="🗑 Delete", callback_data=f"rem_del:{r.id}"),
        ])

    buttons.append([
        InlineKeyboardButton(text="➕ Add Reminder", callback_data="btn_add_reminder"),
        InlineKeyboardButton(text="📰 Today's News", callback_data="btn_news"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def get_settings_keyboard(user: User) -> InlineKeyboardMarkup:
    notif_icon = "🔔 Enabled" if user.missed_reminders_enabled else "🔕 Disabled"
    breaking_icon = "🚨 Enabled" if user.breaking_news_enabled else "🔕 Disabled"

    buttons = [
        [
            InlineKeyboardButton(text=f"📰 News Time ({user.news_time})", callback_data="set_news_time"),
            InlineKeyboardButton(text=f"🌍 Timezone ({user.timezone})", callback_data="set_timezone"),
        ],
        [
            InlineKeyboardButton(text=f"🗣 Language ({user.language.upper()})", callback_data="set_language"),
            InlineKeyboardButton(text=f"Reminders: {notif_icon}", callback_data="toggle_notif"),
        ],
        [
            InlineKeyboardButton(text=f"Breaking Alerts: {breaking_icon}", callback_data="toggle_breaking"),
        ],
        [
            InlineKeyboardButton(text="⏰ Manage Reminders", callback_data="btn_reminders"),
            InlineKeyboardButton(text="📰 Read News", callback_data="btn_news"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_times_keyboard(user: User) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"📰 News Digest: {user.news_time}", callback_data="time_edit:news")],
        [InlineKeyboardButton(text=f"☀️ Morning Challenge: {user.morning_time}", callback_data="time_edit:morning")],
        [InlineKeyboardButton(text=f"🌙 End-of-Day Check: {user.eod_time}", callback_data="time_edit:eod")],
        [InlineKeyboardButton(text="🔙 Back to Settings", callback_data="btn_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_keyboard(is_paused: bool = False) -> InlineKeyboardMarkup:

    pause_text = "▶️ Resume Bot" if is_paused else "⏸ Pause Bot"
    pause_action = "admin_resume" if is_paused else "admin_pause"
    buttons = [
        [InlineKeyboardButton(text="📰 Test News Digest", callback_data="admin_test_news"), InlineKeyboardButton(text="⏰ Test 7 AM", callback_data="admin_test_7am")],
        [InlineKeyboardButton(text="📊 Bot Statistics", callback_data="admin_stats_view"), InlineKeyboardButton(text="📋 News Sources", callback_data="admin_sources_view")],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast_start"), InlineKeyboardButton(text=pause_text, callback_data=pause_action)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action")]])
