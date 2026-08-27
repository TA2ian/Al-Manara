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
    """Reject unauthorized access using only the current Telegram event identity."""
    user = event.from_user
    if user is None:
        return

    user_id = int(user.id)
    message = (
        "⛔ <b>لا تملك صلاحية الإدارة.</b>\n\n"
        f"🆔 معرف حساب Telegram الحالي: <code>{user_id}</code>\n\n"
        "إذا كان هذا هو حساب المشرف، أضف هذا المعرّف إلى "
        "<code>ADMIN_IDS</code> في بيئة تشغيل البوت ثم أعد تشغيل الخدمة."
    )
    if isinstance(event, CallbackQuery):
        await event.answer(message, show_alert=True)
    else:
        await event.answer(message, parse_mode="HTML")


@router.message(Command("admin"))
async def admin_command(message: Message):
    """Handle /admin exclusively from the sender of the current Telegram update."""
    user = message.from_user
    if user is None:
        return
    if not AdminAccessService.is_admin(user.id):
        await _deny(message)
        return
    await _send_admin_menu(message)


@router.message(F.text.func(lambda text: isinstance(text, str) and "⚙" in text))
async def open_admin_from_settings(message: Message):
    user = message.from_user
    if user is None or not AdminAccessService.is_admin(user.id):
        return
    await _send_admin_menu(message)


@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    if user is None or not AdminAccessService.is_admin(user.id):
        await _deny(callback)
        return
    await state.clear()
    await callback.message.edit_text(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=enhanced_admin_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
