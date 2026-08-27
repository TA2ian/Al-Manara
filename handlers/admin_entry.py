"""Authoritative administrator entry points and dashboard navigation."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from keyboards.admin import enhanced_admin_menu_keyboard
from services.admin_access_service import AdminAccessService

router = Router()


async def _send_admin_menu(message: Message) -> None:
    await message.answer(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=enhanced_admin_menu_keyboard(),
        parse_mode="HTML",
    )


async def _deny(event: Message | CallbackQuery) -> None:
    """Reject unauthorized access without exposing the configured allowlist."""
    message = "⛔ لا تملك صلاحية الإدارة."
    if isinstance(event, CallbackQuery):
        await event.answer(message, show_alert=True)
    else:
        await event.answer(message)


@router.message(Command("admin"))
async def admin_command(message: Message):
    if not AdminAccessService.is_admin(message.from_user.id):
        await _deny(message)
        return
    await _send_admin_menu(message)


@router.message(F.text.func(lambda text: isinstance(text, str) and "⚙" in text))
async def open_admin_from_settings(message: Message):
    if not AdminAccessService.is_admin(message.from_user.id):
        return
    await _send_admin_menu(message)


@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    if not AdminAccessService.is_admin(callback.from_user.id):
        await _deny(callback)
        return
    await state.clear()
    await callback.message.edit_text(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=enhanced_admin_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
