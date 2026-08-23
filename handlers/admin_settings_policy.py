"""Authoritative operational admin settings.

Exchange rate is owned by ``admin_rate_policy`` and ShamCash payment accounts
and QR codes are owned by ``payment_methods``. This module contains only
operational settings that have one runtime authority.
"""
from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from keyboards.inline import admin_menu_keyboard, settings_keyboard
from services.settings_service import SettingsService
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _back_to_admin(message: Message):
    await message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")


async def _show_settings(callback: CallbackQuery, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>الإعدادات التشغيلية</b>\n\n"
        "سعر الصرف ووسائل الدفع لهما لوحات مستقلة لتجنب تكرار مسارات الإعداد.",
        reply_markup=settings_keyboard(),
        parse_mode="HTML",
    )


async def _get_decimal_setting(key: str, fallback: float | int) -> Decimal:
    raw = await SettingsService.get(key, str(fallback))
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(str(fallback))


async def _get_timeout_setting() -> int:
    raw = await SettingsService.get("payment_timeout_minutes", str(Config.PAYMENT_TIMEOUT))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = Config.PAYMENT_TIMEOUT
    return max(1, min(value, 1440))


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
    await _show_settings(callback)
    await callback.answer()


@router.callback_query(F.data == "cancel_admin_settings")
async def cancel_admin_settings(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_settings(callback, state)
    await callback.answer()


@router.callback_query(F.data == "setting_fees")
async def setting_fees(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    fee_percent = await _get_decimal_setting("service_fee_percent", Config.SERVICE_FEE_PERCENT)
    await callback.message.edit_text(
        "💰 <b>رسوم الخدمة</b>\n\n"
        f"النسبة الحالية: <b>{fee_percent:g}%</b>\n\n"
        "أرسل نسبة الرسوم الجديدة من 0 إلى 100.\n"
        "تُطبق على عروض الأسعار الجديدة فقط.",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_fee_percent)
    await callback.answer()


@router.message(AdminStates.waiting_fee_percent)
async def admin_set_fee_percent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    try:
        value = Decimal((message.text or "").strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        await message.answer("❌ قيمة غير صالحة. أرسل نسبة بين 0 و100.")
        return
    if value < 0 or value > 100:
        await message.answer("❌ قيمة غير صالحة. أرسل نسبة بين 0 و100.")
        return
    await SettingsService.set("service_fee_percent", str(value))
    await state.clear()
    await message.answer(f"✅ تم تحديث رسوم الخدمة إلى <b>{value:g}%</b>.", parse_mode="HTML")
    await _back_to_admin(message)


@router.callback_query(F.data == "setting_timeout")
async def setting_timeout(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    timeout = await _get_timeout_setting()
    await callback.message.edit_text(
        "⏱ <b>مهلة الدفع</b>\n\n"
        f"المهلة الحالية: <b>{timeout} دقيقة</b>\n\n"
        "أرسل المهلة الجديدة بالدقائق (من 1 إلى 1440).\n"
        "سيتم تطبيقها على الطلبات الجديدة فقط.",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_timeout)
    await callback.answer()


@router.message(AdminStates.waiting_timeout)
async def admin_set_timeout(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    try:
        value = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ قيمة غير صالحة. أرسل عدداً صحيحاً من 1 إلى 1440.")
        return
    if value < 1 or value > 1440:
        await message.answer("❌ قيمة غير صالحة. أرسل عدداً صحيحاً من 1 إلى 1440.")
        return
    await SettingsService.set("payment_timeout_minutes", str(value))
    await state.clear()
    await message.answer(f"✅ تم تحديث مهلة الدفع إلى <b>{value} دقيقة</b>.", parse_mode="HTML")
    await _back_to_admin(message)


@router.callback_query(F.data == "setting_limits")
async def setting_limits(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    minimum = await _get_decimal_setting("min_order", Config.MIN_ORDER)
    maximum = await _get_decimal_setting("max_order", Config.MAX_ORDER)
    daily = await _get_decimal_setting("daily_limit", Config.DAILY_LIMIT)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬇️ الحد الأدنى", callback_data="setting_limit_min"),
            InlineKeyboardButton(text="⬆️ الحد الأقصى", callback_data="setting_limit_max"),
        ],
        [InlineKeyboardButton(text="📅 الحد اليومي", callback_data="setting_limit_daily")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_settings")],
    ])
    await callback.message.edit_text(
        "📊 <b>حدود الطلبات</b>\n\n"
        f"🔹 الحد الأدنى: <b>{minimum:g} USDT</b>\n"
        f"🔹 الحد الأقصى: <b>{maximum:g} USDT</b>\n"
        f"🔹 الحد اليومي للعميل: <b>{daily:g} USDT</b>\n\n"
        "اختر الحد الذي تريد تعديله:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


async def _prompt_limit(callback: CallbackQuery, state: FSMContext, kind: str, title: str, state_name):
    minimum = await _get_decimal_setting("min_order", Config.MIN_ORDER)
    maximum = await _get_decimal_setting("max_order", Config.MAX_ORDER)
    daily = await _get_decimal_setting("daily_limit", Config.DAILY_LIMIT)
    current = {"min": minimum, "max": maximum, "daily": daily}[kind]
    await callback.message.edit_text(
        f"📊 <b>{title}</b>\n\nالقيمة الحالية: <b>{current:g} USDT</b>\n\nأرسل القيمة الجديدة.",
        parse_mode="HTML",
    )
    await state.set_state(state_name)


@router.callback_query(F.data == "setting_limit_min")
async def setting_limit_min(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _prompt_limit(callback, state, "min", "الحد الأدنى للطلب", AdminStates.waiting_min_order)
    await callback.answer()


@router.callback_query(F.data == "setting_limit_max")
async def setting_limit_max(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _prompt_limit(callback, state, "max", "الحد الأقصى للطلب", AdminStates.waiting_max_order)
    await callback.answer()


@router.callback_query(F.data == "setting_limit_daily")
async def setting_limit_daily(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _prompt_limit(callback, state, "daily", "الحد اليومي للعميل", AdminStates.waiting_daily_limit)
    await callback.answer()


async def _save_limit(message: Message, state: FSMContext, key: str, label: str, minimum: Decimal | None = None, maximum: Decimal | None = None):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    try:
        value = Decimal((message.text or "").strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        await message.answer("❌ قيمة غير صالحة. أرسل رقماً أكبر من صفر.")
        return
    if value <= 0:
        await message.answer("❌ القيمة يجب أن تكون أكبر من صفر.")
        return
    if minimum is not None and value < minimum:
        await message.answer(f"❌ {label} يجب ألا يقل عن {minimum:g} USDT.")
        return
    if maximum is not None and value > maximum:
        await message.answer(f"❌ {label} يجب ألا يتجاوز {maximum:g} USDT.")
        return
    await SettingsService.set(key, str(value))
    await state.clear()
    await message.answer(f"✅ تم تحديث {label} إلى <b>{value:g} USDT</b>.", parse_mode="HTML")
    await _back_to_admin(message)


@router.message(AdminStates.waiting_min_order)
async def admin_set_min_order(message: Message, state: FSMContext):
    maximum = await _get_decimal_setting("max_order", Config.MAX_ORDER)
    await _save_limit(message, state, "min_order", "الحد الأدنى للطلب", maximum=maximum)


@router.message(AdminStates.waiting_max_order)
async def admin_set_max_order(message: Message, state: FSMContext):
    minimum = await _get_decimal_setting("min_order", Config.MIN_ORDER)
    daily = await _get_decimal_setting("daily_limit", Config.DAILY_LIMIT)
    await _save_limit(message, state, "max_order", "الحد الأقصى للطلب", minimum=minimum, maximum=daily)


@router.message(AdminStates.waiting_daily_limit)
async def admin_set_daily_limit(message: Message, state: FSMContext):
    maximum = await _get_decimal_setting("max_order", Config.MAX_ORDER)
    await _save_limit(message, state, "daily_limit", "الحد اليومي للعميل", minimum=maximum)
