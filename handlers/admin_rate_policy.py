"""Authoritative exchange-rate admin flow.

Completes the FSM transaction in-place: after a successful update the
input prompt is replaced by a confirmation screen and the FSM is cleared.
"""
from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard
from services.exchange_service import ExchangeService
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء والعودة للوحة التحكم", callback_data="admin_cancel_input")]
    ])


async def _current_rate() -> Decimal:
    pool = await get_pool()
    if not pool:
        return Decimal("0")
    return await ExchangeService(pool).get_current_rate()


async def _start_rate_input(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    rate = await _current_rate()
    await state.clear()
    await callback.message.edit_text(
        f"💱 <b>سعر الصرف الحالي:</b> 1 USDT = {rate:,.2f} NEW.SYP\n\n"
        "أرسل السعر الجديد:",
        reply_markup=_cancel_keyboard(),
        parse_mode="HTML",
    )
    # Keep the prompt message ID so the transaction closes visually in-place.
    await state.update_data(rate_prompt_message_id=callback.message.message_id)
    await state.set_state(AdminStates.waiting_rate)
    await callback.answer()


@router.callback_query(F.data == "setting_rate")
@router.callback_query(F.data == "admin_update_rate")
async def rate_settings_start(callback: CallbackQuery, state: FSMContext):
    await _start_rate_input(callback, state)


@router.message(AdminStates.waiting_rate)
async def rate_settings_save(message: Message, state: FSMContext):
    """Validate, persist, and immediately close the rate-input transaction."""
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
        if prompt_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_id,
                    text=(
                        "❌ <b>سعر غير صالح</b>\n\n"
                        "أرسل رقماً أكبر من صفر.\n"
                        "مثال: <code>150.50</code>"
                    ),
                    reply_markup=_cancel_keyboard(),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        else:
            await message.answer("❌ سعر غير صالح. أرسل رقماً أكبر من صفر.", reply_markup=_cancel_keyboard())
        return

    pool = await get_pool()
    service = ExchangeService(pool)
    success = await service.update_rate(value, message.from_user.id)

    data = await state.get_data()
    prompt_id = data.get("rate_prompt_message_id")
    await state.clear()

    if not success:
        text = (
            "❌ <b>تعذر تحديث سعر الصرف</b>\n\n"
            "لم يتم تغيير السعر. حاول مرة أخرى من لوحة التحكم."
        )
        if prompt_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_id,
                    text=text,
                    reply_markup=admin_menu_keyboard(),
                    parse_mode="HTML",
                )
            except Exception:
                await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="HTML")
        return

    formatted = f"{value:,.8f}".rstrip("0").rstrip(".")
    text = (
        "✅ <b>تم تحديث سعر الصرف بنجاح</b>\n\n"
        f"💱 1 USDT = <b>{formatted} NEW.SYP</b>\n\n"
        "تم حفظ السعر وتطبيقه على عروض الأسعار الجديدة."
    )

    if prompt_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_id,
                text=text,
                reply_markup=admin_menu_keyboard(),
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=admin_menu_keyboard(), parse_mode="HTML")
