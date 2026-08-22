"""Authoritative exchange-rate admin flow."""
from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard
from services.exchange_service import ExchangeService
from services.formatters import rate
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء والعودة للوحة التحكم", callback_data="admin_cancel_input")]])


async def _current_rate() -> Decimal:
    pool = await get_pool()
    if not pool:
        return Decimal("0")
    return await ExchangeService(pool).get_current_rate()


@router.callback_query(F.data == "setting_rate")
@router.callback_query(F.data == "admin_update_rate")
async def rate_settings_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    current = await _current_rate()
    await state.clear()
    await callback.message.edit_text(
        f"💱 <b>سعر الصرف الحالي:</b> 1 USD = {rate(current)} NEW.SYP\n\n"
        "أرسل سعر NEW.SYP مقابل 1 USD:",
        reply_markup=_cancel_keyboard(),
        parse_mode="HTML",
    )
    await state.update_data(rate_prompt_message_id=callback.message.message_id)
    await state.set_state(AdminStates.waiting_rate)
    await callback.answer()


@router.message(AdminStates.waiting_rate)
async def rate_settings_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    raw = (message.text or "").strip().replace(",", "")
    try:
        value = Decimal(raw)
        if value <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        data = await state.get_data()
        prompt_id = data.get("rate_prompt_message_id")
        text = "❌ <b>سعر غير صالح</b>\n\nأرسل رقماً أكبر من صفر.\nمثال: <code>150.50</code>"
        if prompt_id:
            try:
                await message.bot.edit_message_text(chat_id=message.chat.id, message_id=prompt_id, text=text, reply_markup=_cancel_keyboard(), parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=_cancel_keyboard(), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=_cancel_keyboard(), parse_mode="HTML")
        return

    pool = await get_pool()
    success = await ExchangeService(pool).update_rate(value, message.from_user.id)
    data = await state.get_data()
    prompt_id = data.get("rate_prompt_message_id")
    await state.clear()

    text = (
        "❌ <b>تعذر تحديث سعر الصرف</b>\n\nلم يتم تغيير السعر. حاول مرة أخرى من لوحة التحكم."
        if not success else
        "✅ <b>تم تحديث سعر الصرف بنجاح</b>\n\n"
        f"💱 1 USD = <b>{rate(value)} NEW.SYP</b>\n\n"
        "تم حفظ السعر وتطبيقه على عروض الأسعار الجديدة."
    )
    if prompt_id:
        try:
            await message.bot.edit_message_text(chat_id=message.chat.id, message_id=prompt_id, text=text, reply_markup=admin_menu_keyboard(), parse_mode="HTML")
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="HTML")
