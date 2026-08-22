"""Authoritative admin settings policy for ShamCash and operational settings.

Fee, exchange-rate, timeout, and order-limit inputs are owned by
``admin_navigation_policy``. Keeping them here would register duplicate FSM
and callback handlers through the admin compatibility facade.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from keyboards.inline import admin_menu_keyboard, settings_keyboard
from services.settings_service import SettingsService
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _back_to_admin(message: Message):
    await message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        return
    await message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_settings")
async def admin_settings_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        "⚙️ <b>الإعدادات</b>\nاختر الإعداد الذي تريد تعديله:",
        reply_markup=settings_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_admin_settings")
async def cancel_admin_settings(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>الإعدادات</b>\nاختر الإعداد الذي تريد تعديله:",
        reply_markup=settings_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "setting_shamcash_usd")
async def setting_shamcash_usd(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"📱 <b>حساب شام كاش USD الحالي:</b>\n<code>{Config.get_shamcash_usd()}</code>\n\nأرسل رقم الحساب الجديد:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_shamcash_usd)
    await callback.answer()


@router.message(AdminStates.waiting_shamcash_usd)
async def admin_set_shamcash_usd(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    account = (message.text or "").strip()
    if not account:
        await message.answer("❌ رقم الحساب فارغ.")
        return
    Config.SHAMCASH_USD_ACCOUNT = account
    Config.set_shamcash_usd(account)
    await SettingsService.set("shamcash_usd", account)
    await message.answer(f"✅ تم تحديث حساب شام كاش USD:\n<code>{account}</code>", parse_mode="HTML")
    await state.clear()
    await _back_to_admin(message)


@router.callback_query(F.data == "setting_shamcash_syp")
async def setting_shamcash_syp(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"📱 <b>حساب شام كاش NEW.SYP الحالي:</b>\n<code>{Config.get_shamcash_syp()}</code>\n\nأرسل رقم الحساب الجديد لعملة NEW.SYP:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_shamcash_syp)
    await callback.answer()


@router.message(AdminStates.waiting_shamcash_syp)
async def admin_set_shamcash_syp(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    account = (message.text or "").strip()
    if not account:
        await message.answer("❌ رقم الحساب فارغ.")
        return
    Config.SHAMCASH_SYP_ACCOUNT = account
    Config.set_shamcash_syp(account)
    await SettingsService.set("shamcash_syp", account)
    await message.answer(f"✅ تم تحديث حساب شام كاش NEW.SYP:\n<code>{account}</code>", parse_mode="HTML")
    await state.clear()
    await _back_to_admin(message)


@router.callback_query(F.data == "setting_shamcash_name")
async def setting_shamcash_name(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"👤 <b>اسم حساب شام كاش الحالي:</b>\n{Config.get_shamcash_name() or 'N/A'}\n\nأرسل الاسم الجديد:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_shamcash_name)
    await callback.answer()


@router.message(AdminStates.waiting_shamcash_name)
async def admin_set_shamcash_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ الاسم فارغ.")
        return
    Config.SHAMCASH_NAME = name
    Config.set_shamcash_name(name)
    await SettingsService.set("shamcash_name", name)
    await message.answer(f"✅ تم تحديث اسم حساب شام كاش: {name}")
    await state.clear()
    await _back_to_admin(message)
