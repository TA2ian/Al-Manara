"""Authoritative admin entry points."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import Config
from keyboards.inline import admin_menu_keyboard

router = Router()


async def _send_admin_menu(message: Message) -> None:
    await message.answer(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("admin"))
async def admin_command(message: Message):
    """Open the single authoritative admin dashboard."""
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.answer("⛔ Access denied")
        return
    await _send_admin_menu(message)


@router.message(F.text.func(lambda text: isinstance(text, str) and "⚙" in text))
async def open_admin_from_settings(message: Message):
    """Open the admin dashboard from the settings control for administrators."""
    if message.from_user.id not in Config.ADMIN_IDS:
        return
    await _send_admin_menu(message)
