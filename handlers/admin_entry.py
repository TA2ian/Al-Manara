"""Authoritative admin entry points and dashboard navigation."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.filters import Command

from config import Config
from keyboards.inline import admin_menu_keyboard

router = Router()


def enhanced_admin_menu_keyboard() -> InlineKeyboardMarkup:
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


async def _send_admin_menu(message: Message) -> None:
    await message.answer(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=enhanced_admin_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.answer("⛔ Access denied")
        return
    await _send_admin_menu(message)


@router.message(F.text.func(lambda text: isinstance(text, str) and "⚙" in text))
async def open_admin_from_settings(message: Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        return
    await _send_admin_menu(message)


@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in Config.ADMIN_IDS:
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=enhanced_admin_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
