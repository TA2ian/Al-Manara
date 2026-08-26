"""Authoritative operational admin settings."""
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from keyboards.admin import enhanced_admin_menu_keyboard
from keyboards.inline import settings_keyboard
from services.operational_policy_service import OperationalPolicyError, OperationalPolicyService
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _back_to_admin(message: Message) -> None:
    await message.answer(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=enhanced_admin_menu_keyboard(),
        parse_mode="HTML",
    )


async def _show_settings(callback: CallbackQuery, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>الإعدادات التشغيلية</b>\n\n"
        "هذه الإعدادات تؤثر على الطلبات الجديدة فقط. الرسوم والمهلة والحدود تستخدم نفس المصدر التشغيلي في الحساب والـorder flow.",
        reply_markup=settings_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_settings")
async def admin_settings_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_settings(callback)
    await callback.answer()


@router.callback_query(F.data == "cancel_admin_settings")
async def cancel_admin_settings(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_settings(callback, state)
    await callback.answer()


@router.callback_query(F.data == "setting_fees")
async def setting_fees(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    fee_percent = await OperationalPolicyService.get_fee_percent()
    await callback.message.edit_text(
        "💰 <b>رسوم الخدمة</b>\n\n"
        f"النسبة الحالية: <b>{fee_percent:g}%</b>\n\n"
        "أرسل نسبة الرسوم الجديدة من 0 إلى 100.\n"
        "سيتم استخدامها في عروض الأسعار والطلبات الجديدة، بينما تبقى الرسوم المثبتة في الطلبات السابقة دون تغيير.",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_fee_percent)
    await callback.answer()


@router.message(AdminStates.waiting_fee_percent)
async def admin_set_fee_percent(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    try:
        value = Decimal((message.text or "").strip().replace(",", ""))
        saved = await OperationalPolicyService.set_fee_percent(value, message.from_user.id)
    except (OperationalPolicyError, ValueError):
        await message.answer("❌ قيمة غير صالحة. أرسل نسبة بين 0 و100.")
        return
    await state.clear()
    await message.answer(f"✅ تم تحديث رسوم الخدمة إلى <b>{saved:g}%</b>.", parse_mode="HTML")
    await _back_to_admin(message)


@router.callback_query(F.data == "setting_timeout")
async def setting_timeout(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    timeout = await OperationalPolicyService.get_payment_timeout_minutes()
    await callback.message.edit_text(
        "⏱ <b>مهلة الدفع</b>\n\n"
        f"المهلة الحالية: <b>{timeout} دقيقة</b>\n\n"
        "أرسل المهلة الجديدة بالدقائق من 1 إلى 1440.\n"
        "تُطبق عند اعتماد الطلبات الجديدة ولا تغيّر المهل المثبتة للطلبات القائمة.",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_timeout)
    await callback.answer()


@router.message(AdminStates.waiting_timeout)
async def admin_set_timeout(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    try:
        saved = await OperationalPolicyService.set_payment_timeout(message.text or "", message.from_user.id)
    except OperationalPolicyError:
        await message.answer("❌ قيمة غير صالحة. أرسل عدداً صحيحاً من 1 إلى 1440.")
        return
    await state.clear()
    await message.answer(f"✅ تم تحديث مهلة الدفع إلى <b>{saved} دقيقة</b>.", parse_mode="HTML")
    await _back_to_admin(message)


@router.callback_query(F.data == "setting_limits")
async def setting_limits(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    limits = await OperationalPolicyService.get_limits()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬇️ الحد الأدنى", callback_data="setting_limit_min"), InlineKeyboardButton(text="⬆️ الحد الأقصى", callback_data="setting_limit_max")],
        [InlineKeyboardButton(text="📅 الحد اليومي", callback_data="setting_limit_daily")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_settings")],
    ])
    await callback.message.edit_text(
        "📊 <b>حدود الطلبات</b>\n\n"
        f"🔹 الحد الأدنى: <b>{limits['min_order']:g} USDT</b>\n"
        f"🔹 الحد الأقصى: <b>{limits['max_order']:g} USDT</b>\n"
        f"🔹 الحد اليومي للعميل: <b>{limits['daily_limit']:g} USDT</b>\n\n"
        "يجب دائماً أن يكون: الحد الأدنى ≤ الحد الأقصى ≤ الحد اليومي.",
        reply_markup=keyboard, parse_mode="HTML",
    )
    await callback.answer()


async def _prompt_limit(callback: CallbackQuery, state: FSMContext, kind: str, title: str, state_name) -> None:
    limits = await OperationalPolicyService.get_limits()
    current = limits[kind if kind != "min" else "min_order"] if kind in {"min_order", "max_order", "daily_limit"} else {"min": limits["min_order"], "max": limits["max_order"], "daily": limits["daily_limit"]}[kind]
    await callback.message.edit_text(
        f"📊 <b>{title}</b>\n\nالقيمة الحالية: <b>{current:g} USDT</b>\n\nأرسل القيمة الجديدة.",
        parse_mode="HTML",
    )
    await state.set_state(state_name)


@router.callback_query(F.data == "setting_limit_min")
async def setting_limit_min(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _prompt_limit(callback, state, "min", "الحد الأدنى للطلب", AdminStates.waiting_min_order)
    await callback.answer()


@router.callback_query(F.data == "setting_limit_max")
async def setting_limit_max(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _prompt_limit(callback, state, "max", "الحد الأقصى للطلب", AdminStates.waiting_max_order)
    await callback.answer()


@router.callback_query(F.data == "setting_limit_daily")
async def setting_limit_daily(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _prompt_limit(callback, state, "daily", "الحد اليومي للعميل", AdminStates.waiting_daily_limit)
    await callback.answer()


async def _save_limit(message: Message, state: FSMContext, key: str, label: str) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    try:
        saved = await OperationalPolicyService.set_limit(key, message.text or "", message.from_user.id)
    except OperationalPolicyError as exc:
        messages = {
            "Minimum order cannot be below maximum order": "❌ الحد الأدنى لا يمكن أن يتجاوز الحد الأقصى الحالي.",
            "Daily limit cannot be below maximum order": "❌ الحد اليومي يجب أن يكون أكبر من أو يساوي الحد الأقصى للطلب.",
        }
        await message.answer(messages.get(str(exc), "❌ القيمة غير صالحة. راجع الحدود الحالية ثم أرسل قيمة متوافقة."))
        return
    await state.clear()
    await message.answer(f"✅ تم تحديث {label} إلى <b>{saved:g} USDT</b>.", parse_mode="HTML")
    await _back_to_admin(message)


@router.message(AdminStates.waiting_min_order)
async def admin_set_min_order(message: Message, state: FSMContext) -> None:
    await _save_limit(message, state, "min_order", "الحد الأدنى للطلب")


@router.message(AdminStates.waiting_max_order)
async def admin_set_max_order(message: Message, state: FSMContext) -> None:
    await _save_limit(message, state, "max_order", "الحد الأقصى للطلب")


@router.message(AdminStates.waiting_daily_limit)
async def admin_set_daily_limit(message: Message, state: FSMContext) -> None:
    await _save_limit(message, state, "daily_limit", "الحد اليومي للعميل")
