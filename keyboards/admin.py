"""Shared administrator navigation keyboards."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.inline import admin_menu_keyboard


def enhanced_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Return the canonical admin dashboard with the payment-method entry."""
    rows = []
    for row in admin_menu_keyboard().inline_keyboard:
        new_row = []
        for button in row:
            if button.callback_data == "admin_analytics":
                new_row.append(InlineKeyboardButton(text="📈 التحليل المالي", callback_data="admin_analytics"))
            else:
                new_row.append(button)
        rows.append(new_row)
    rows.insert(3, [InlineKeyboardButton(text="💳 وسائل الدفع", callback_data="admin_payment_methods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
