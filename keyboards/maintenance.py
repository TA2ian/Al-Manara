"""Keyboards for Maintenance 2.0."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def maintenance_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    rows = []
    if current_mode != "limited":
        rows.append([InlineKeyboardButton(text="🟡 تشغيل محدود", callback_data="admin_maintenance_mode_limited")])
    if current_mode != "maintenance":
        rows.append([InlineKeyboardButton(text="🛠️ صيانة كاملة", callback_data="admin_maintenance_mode_maintenance")])
    if current_mode != "emergency":
        rows.append([InlineKeyboardButton(text="🚨 طوارئ", callback_data="admin_maintenance_mode_emergency")])
    if current_mode != "off":
        rows.append([InlineKeyboardButton(text="✅ العودة للوضع الطبيعي", callback_data="admin_maintenance_mode_off")])
    rows.append([InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def maintenance_confirm_keyboard(mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تأكيد التغيير", callback_data=f"admin_maintenance_confirm_{mode}")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_menu")],
    ])
