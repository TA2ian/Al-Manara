"""Keyboards for canonical admin messaging flows."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def message_template_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 تحديث", callback_data=f"{prefix}_template_update")],
        [InlineKeyboardButton(text="ℹ️ تنبيه خدمي", callback_data=f"{prefix}_template_service")],
        [InlineKeyboardButton(text="🛠️ صيانة", callback_data=f"{prefix}_template_maintenance")],
        [InlineKeyboardButton(text="⚠️ تنبيه مهم", callback_data=f"{prefix}_template_important")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_broadcast_cancel")],
    ])


def personal_message_keyboard(telegram_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    action = "admin_unban_" if is_blocked else "admin_ban_"
    action_text = "✅ فك الحظر" if is_blocked else "🚫 حظر"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ رسالة خاصة", callback_data=f"admin_personal_message_{telegram_id}")],
        [
            InlineKeyboardButton(text=action_text, callback_data=f"{action}{telegram_id}"),
            InlineKeyboardButton(text="🗑️ حذف العميل", callback_data=f"admin_del_user_{telegram_id}"),
        ],
        [InlineKeyboardButton(text="🔍 بحث عميل آخر", callback_data="admin_search_user")],
        [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
    ])


def personal_message_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 إرسال للعميل", callback_data="admin_personal_message_send")],
        [InlineKeyboardButton(text="✏️ تعديل", callback_data="admin_personal_message_edit"), InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_personal_message_cancel")],
    ])
