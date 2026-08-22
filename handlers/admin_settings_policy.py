"""Authoritative admin settings policy for non-rate operational settings."""
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
    await callback.message.edit_text("⚙️ <b>الإعدادات</b>\nاختر الإعداد الذي تريد تعديله:", reply_markup=settings_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_menu")
async def admin_menu_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "setting_fees")
async def setting_fees(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    current_percent = await SettingsService.get("service_fee_percent", str(Config.SERVICE_FEE_PERCENT))
    current_fixed = await SettingsService.get("service_fee_fixed", str(Config.SERVICE_FEE_FIXED))
    await callback.message.edit_text(
        "⚙️ <b>الرسوم الحالية</b>\n\n"
        f"📊 نسبة: <b>{current_percent}%</b>\n"
        f"💵 ثابت: <b>{current_fixed}</b>\n\n"
        "أرسل نسبة الرسوم الجديدة من 0 إلى 100.",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_fee_percent)
    await callback.answer()


@router.message(AdminStates.waiting_fee_percent)
async def admin_set_fee_percent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); await message.answer("⛔ Access denied"); return
    try:
        pct = float((message.text or "").strip())
        if not 0 <= pct <= 100: raise ValueError
    except ValueError:
        await message.answer("❌ نسبة غير صالحة (0-100). أرسل رقماً صحيحاً:")
        return
    Config.SERVICE_FEE_PERCENT = pct
    await SettingsService.set("service_fee_percent", str(pct))
    await message.answer(f"✅ تم حفظ نسبة الرسوم: <b>{pct:g}%</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_fee_fixed)
    await message.answer("💵 أرسل الرسوم الثابتة الجديدة:")


@router.message(AdminStates.waiting_fee_fixed)
async def admin_set_fee_fixed(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); await message.answer("⛔ Access denied"); return
    try:
        fixed = float((message.text or "").strip())
        if fixed < 0: raise ValueError
    except ValueError:
        await message.answer("❌ قيمة غير صالحة. أرسل رقماً صفراً أو أكبر:")
        return
    Config.SERVICE_FEE_FIXED = fixed
    await SettingsService.set("service_fee_fixed", str(fixed))
    await message.answer(f"✅ تم حفظ الرسوم الثابتة: <b>{fixed:g}</b>", parse_mode="HTML")
    await state.clear(); await _back_to_admin(message)


@router.callback_query(F.data == "setting_shamcash_usd")
async def setting_shamcash_usd(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    await callback.message.edit_text(
        f"📱 <b>حساب شام كاش USD الحالي:</b>\n<code>{Config.get_shamcash_usd()}</code>\n\nأرسل رقم الحساب الجديد:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_shamcash_usd); await callback.answer()


@router.message(AdminStates.waiting_shamcash_usd)
async def admin_set_shamcash_usd(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); await message.answer("⛔ Access denied"); return
    account = (message.text or "").strip()
    if not account:
        await message.answer("❌ رقم الحساب فارغ."); return
    Config.SHAMCASH_USD_ACCOUNT = account
    Config.set_shamcash_usd(account)
    await SettingsService.set("shamcash_usd", account)
    await message.answer(f"✅ تم تحديث حساب شام كاش USD:\n<code>{account}</code>", parse_mode="HTML")
    await state.clear(); await _back_to_admin(message)


@router.callback_query(F.data == "setting_shamcash_syp")
async def setting_shamcash_syp(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    await callback.message.edit_text(
        f"📱 <b>حساب شام كاش SYP الحالي:</b>\n<code>{Config.get_shamcash_syp()}</code>\n\nأرسل رقم الحساب الجديد:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_shamcash_syp); await callback.answer()


@router.message(AdminStates.waiting_shamcash_syp)
async def admin_set_shamcash_syp(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); await message.answer("⛔ Access denied"); return
    account = (message.text or "").strip()
    if not account:
        await message.answer("❌ رقم الحساب فارغ."); return
    Config.SHAMCASH_SYP_ACCOUNT = account
    Config.set_shamcash_syp(account)
    await SettingsService.set("shamcash_syp", account)
    await message.answer(f"✅ تم تحديث حساب شام كاش SYP:\n<code>{account}</code>", parse_mode="HTML")
    await state.clear(); await _back_to_admin(message)


@router.callback_query(F.data == "setting_shamcash_name")
async def setting_shamcash_name(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    await callback.message.edit_text(
        f"👤 <b>اسم حساب شام كاش الحالي:</b>\n{Config.get_shamcash_name() or 'N/A'}\n\nأرسل الاسم الجديد:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_shamcash_name); await callback.answer()


@router.message(AdminStates.waiting_shamcash_name)
async def admin_set_shamcash_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); await message.answer("⛔ Access denied"); return
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ الاسم فارغ."); return
    Config.SHAMCASH_NAME = name
    Config.set_shamcash_name(name)
    await SettingsService.set("shamcash_name", name)
    await message.answer(f"✅ تم تحديث اسم حساب شام كاش: {name}")
    await state.clear(); await _back_to_admin(message)


@router.callback_query(F.data == "setting_timeout")
async def setting_timeout(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    await callback.message.edit_text(
        f"⏱ <b>مهلة الدفع الحالية:</b> {Config.PAYMENT_TIMEOUT} دقيقة\n\nأرسل المهلة الجديدة بالدقائق:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_timeout); await callback.answer()


@router.message(AdminStates.waiting_timeout)
async def admin_set_timeout(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); await message.answer("⛔ Access denied"); return
    try:
        timeout = int((message.text or "").strip())
        if not 1 <= timeout <= 1440: raise ValueError
    except ValueError:
        await message.answer("❌ قيمة غير صالحة (1-1440 دقيقة). أرسل رقماً صحيحاً:"); return
    Config.PAYMENT_TIMEOUT = timeout
    await SettingsService.set("payment_timeout", str(timeout))
    await message.answer(f"✅ تم حفظ مهلة الدفع: <b>{timeout} دقيقة</b>", parse_mode="HTML")
    await state.clear(); await _back_to_admin(message)


@router.callback_query(F.data == "setting_limits")
async def setting_limits(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    await callback.message.edit_text(
        f"📊 <b>الحدود الحالية</b>\n\n🔽 الحد الأدنى: {Config.MIN_ORDER} USDT\n🔼 الحد الأقصى: {Config.MAX_ORDER} USDT\n\nأرسل الحد الأدنى الجديد:",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_min_order); await callback.answer()


@router.message(AdminStates.waiting_min_order)
async def admin_set_min_order(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); await message.answer("⛔ Access denied"); return
    try:
        value = float((message.text or "").strip())
        if value < 1: raise ValueError
    except ValueError:
        await message.answer("❌ قيمة غير صالحة. أرسل رقماً صحيحاً (1+):"); return
    Config.MIN_ORDER = value
    await SettingsService.set("min_order", str(value))
    await message.answer(f"✅ تم حفظ الحد الأدنى: <b>{value:g} USDT</b>\n\nأرسل الحد الأقصى الجديد:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_max_order)


@router.message(AdminStates.waiting_max_order)
async def admin_set_max_order(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); await message.answer("⛔ Access denied"); return
    try:
        value = float((message.text or "").strip())
        if value < Config.MIN_ORDER: raise ValueError
    except ValueError:
        await message.answer(f"❌ قيمة غير صالحة. أرسل رقماً أكبر من الحد الأدنى ({Config.MIN_ORDER}):"); return
    Config.MAX_ORDER = value
    await SettingsService.set("max_order", str(value))
    await message.answer(f"✅ تم حفظ الحد الأقصى: <b>{value:g} USDT</b>", parse_mode="HTML")
    await state.clear(); await _back_to_admin(message)
