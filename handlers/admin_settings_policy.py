"""Authoritative operational admin settings."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from keyboards.admin import enhanced_admin_menu_keyboard
from keyboards.inline import settings_keyboard
from services.operational_policy_service import OperationalPolicyError, OperationalPolicyService
from states import AdminStates

router = Router()
SUPPORTED_FEE_NETWORKS = ("BEP20", "TRC20", "ARB", "SOLANA", "ETH", "POLYGON")


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _back_to_admin(message: Message) -> None:
    await message.answer("👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:", reply_markup=enhanced_admin_menu_keyboard(), parse_mode="HTML")


async def _show_settings(callback: CallbackQuery, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>الإعدادات التشغيلية</b>\n\nإعدادات الرسوم والمهلة والحدود تؤثر على الطلبات الجديدة فقط. رسوم الخدمة ورسوم الشبكة الثابتة مستقلة لكل شبكة.",
        reply_markup=settings_keyboard(), parse_mode="HTML",
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
    await state.clear()
    rows = []
    for network in SUPPORTED_FEE_NETWORKS:
        rows.append([InlineKeyboardButton(text=network, callback_data=f"setting_fee_network_{network}")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_settings")])
    await callback.message.edit_text(
        "💰 <b>رسوم الشبكات</b>\n\nلكل شبكة رسم خدمة بنسبة يحددها الأدمن، ورسم شبكة ثابت يحدده الأدمن. اختر الشبكة لإدارة القيمتين.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setting_fee_network_"))
async def setting_fee_network(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    network = callback.data.removeprefix("setting_fee_network_")
    if network not in SUPPORTED_FEE_NETWORKS:
        await callback.answer("Unknown network", show_alert=True)
        return
    policy = await OperationalPolicyService.get_network_fee_policy(network)
    await state.update_data(fee_network=network)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تعديل رسوم الخدمة %", callback_data="edit_service_fee")],
        [InlineKeyboardButton(text="تعديل الرسم الثابت USDT", callback_data="edit_fixed_network_fee")],
        [InlineKeyboardButton(text="🔙 الشبكات", callback_data="setting_fees")],
    ])
    await callback.message.edit_text(
        f"💰 <b>{network}</b>\n\n"
        f"رسوم الخدمة: <b>{policy.service_fee_percent:g}%</b>\n"
        f"الرسم الثابت: <b>{policy.fixed_network_fee_usdt:g} USDT</b>\n\n"
        "اختر القيمة التي تريد تعديلها.",
        reply_markup=keyboard, parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "edit_service_fee")
async def edit_service_fee(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    data = await state.get_data()
    network = data.get("fee_network")
    if network not in SUPPORTED_FEE_NETWORKS:
        await callback.answer("اختر الشبكة أولًا", show_alert=True)
        return
    current = await OperationalPolicyService.get_fee_percent(network)
    await callback.message.edit_text(f"💰 <b>رسوم الخدمة — {network}</b>\n\nالقيمة الحالية: <b>{current:g}%</b>\n\nأرسل النسبة الجديدة.", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_fee_percent)
    await callback.answer()


@router.message(AdminStates.waiting_fee_percent)
async def admin_set_fee_percent(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    data = await state.get_data()
    network = data.get("fee_network")
    try:
        saved = await OperationalPolicyService.set_fee_percent(message.text or "", message.from_user.id, network=network)
    except OperationalPolicyError as exc:
        await message.answer(f"❌ {exc}")
        return
    await state.clear()
    await message.answer(f"✅ تم تحديث رسوم الخدمة لشبكة {network} إلى <b>{saved:g}%</b>.", parse_mode="HTML")
    await _back_to_admin(message)


@router.callback_query(F.data == "edit_fixed_network_fee")
async def edit_fixed_network_fee(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    data = await state.get_data()
    network = data.get("fee_network")
    if network not in SUPPORTED_FEE_NETWORKS:
        await callback.answer("اختر الشبكة أولًا", show_alert=True)
        return
    current = await OperationalPolicyService.get_fixed_fee_usdt(network)
    await callback.message.edit_text(f"💰 <b>الرسم الثابت — {network}</b>\n\nالقيمة الحالية: <b>{current:g} USDT</b>\n\nأرسل القيمة الجديدة بـUSDT.", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_fixed_network_fee)
    await callback.answer()


@router.message(AdminStates.waiting_fixed_network_fee)
async def admin_set_fixed_network_fee(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    data = await state.get_data()
    network = data.get("fee_network")
    try:
        saved = await OperationalPolicyService.set_fixed_fee_usdt(message.text or "", message.from_user.id, network=network)
    except OperationalPolicyError as exc:
        await message.answer(f"❌ {exc}")
        return
    await state.clear()
    await message.answer(f"✅ تم تحديث الرسم الثابت لشبكة {network} إلى <b>{saved:g} USDT</b>.", parse_mode="HTML")
    await _back_to_admin(message)


@router.callback_query(F.data == "setting_timeout")
async def setting_timeout(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    timeout = await OperationalPolicyService.get_payment_timeout_minutes()
    await callback.message.edit_text("⏱ <b>مهلة الدفع</b>\n\n" f"المهلة الحالية: <b>{timeout} دقيقة</b>\n\nأرسل المهلة الجديدة بالدقائق من 1 إلى 1440.", parse_mode="HTML")
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
    await callback.message.edit_text("📊 <b>حدود الطلبات</b>\n\n" f"🔹 الحد الأدنى: <b>{limits['min_order']:g} USDT</b>\n" f"🔹 الحد الأقصى: <b>{limits['max_order']:g} USDT</b>\n" f"🔹 الحد اليومي للعميل: <b>{limits['daily_limit']:g} USDT</b>\n\nيجب دائماً أن يكون: الحد الأدنى ≤ الحد الأقصى ≤ الحد اليومي.", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


async def _prompt_limit(callback: CallbackQuery, state: FSMContext, kind: str, title: str, state_name) -> None:
    limits = await OperationalPolicyService.get_limits()
    current = {"min": limits["min_order"], "max": limits["max_order"], "daily": limits["daily_limit"]}[kind]
    await callback.message.edit_text(f"📊 <b>{title}</b>\n\nالقيمة الحالية: <b>{current:g} USDT</b>\n\nأرسل القيمة الجديدة.", parse_mode="HTML")
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
    await _save_limit(message, state, "daily_limit", "الحد اليومي للطلب")
