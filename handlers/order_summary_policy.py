"""Authoritative customer order-summary presentation policy.

Runs before the legacy order currency handler so the customer sees an
unambiguous USD/NEW.SYP breakdown, the amount received before the base amount,
and a visually prominent amount to send.
"""
from decimal import Decimal

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import order_confirmation_keyboard
from services.exchange_service import ExchangeService
from services.locale_service import locale_service
from states import OrderStates

router = Router()


async def _get_lang(user_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1", user_id
        )
    return (row["language"] if row and row["language"] else "ar")


def _money(value) -> str:
    return f"{Decimal(str(value)):,.2f}"


@router.callback_query(OrderStates.waiting_currency, F.data.startswith("currency_"))
async def show_authoritative_order_summary(callback: CallbackQuery, state: FSMContext):
    """Calculate and render the customer-facing payment summary."""
    currency = callback.data.replace("currency_", "")
    lang = await _get_lang(callback.from_user.id)
    data = await state.get_data()

    pool = await get_pool()
    calculation = await ExchangeService(pool).calculate_order(
        data["amount_usdt"], currency
    )
    await state.update_data(payment_currency=currency, calculation=calculation)

    network = data.get("network", "")
    if network == "TRC20":
        network_display = "🔷 TRC20 (TRX)"
    elif network == "BEP20":
        network_display = "🟡 BEP20 (BNB)"
    else:
        network_display = network

    rate = calculation["exchange_rate"]
    base = calculation["base_amount"]
    fee = calculation["fee_amount"]
    fee_pct = calculation["fee_percent"]
    total = calculation["total_amount"]

    if currency == "NEW.SYP":
        currency_name = "🇸🇾 الليرة السورية الجديدة (NEW.SYP)"
        rate_block = (
            "──── 💱 سعر الصرف ────\n"
            "🇺🇸 الدولار الأمريكي (USD): <b>1.00 USD</b>\n"
            f"🇸🇾 الليرة السورية الجديدة (NEW.SYP): <b>{_money(rate)} NEW.SYP</b>\n"
            f"🔄 <b>1 USD = {_money(rate)} NEW.SYP</b>\n"
        )
        base_unit = "NEW.SYP"
    else:
        currency_name = "🇺🇸 الدولار الأمريكي (USD)"
        rate_block = (
            "──── 💱 سعر الصرف ────\n"
            "🇺🇸 الدولار الأمريكي (USD): <b>1.00 USD</b>\n"
            f"🇸🇾 الليرة السورية الجديدة (NEW.SYP): <b>{_money(rate)} NEW.SYP</b>\n"
            f"🔄 <b>1 USD = {_money(rate)} NEW.SYP</b>\n"
        )
        base_unit = "USD"

    # Keep the requested semantic order: the customer first sees what they
    # receive, then the base amount used to calculate the payment, then fees,
    # and finally the amount that must actually be sent.
    summary = (
        f"📋 <b>ملخص طلبك #PENDING</b>\n\n"
        "──── 💳 معلومات USDT ────\n"
        f"💰 المبلغ: <b>{data['amount_usdt']} USDT</b>\n"
        f"🌐 الشبكة: {network_display}\n"
        f"📍 العنوان: <code>{data['wallet_address']}</code>\n\n"
        f"{rate_block}\n"
        f"💳 عملة الدفع: <b>{currency_name}</b>\n\n"
        "👇 <b>المبلغ الذي سيصل إليك:</b>\n"
        f"💰 <b>{_money(data['amount_usdt'])} USDT</b>\n\n"
        "──── 💵 المبلغ الأساسي ────\n"
        f"💵 <b>{_money(base)} {base_unit}</b>\n\n"
        "──── 💰 رسوم الخدمة ────\n"
        f"📊 النسبة: <b>{_money(fee_pct)}%</b>\n"
        f"💵 قيمة الرسوم: <b>{_money(fee)} {base_unit}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💸 <b>المجموع الإجمالي — المبلغ المطلوب إرساله:</b>\n"
        f"<b>💰 {_money(total)} {base_unit}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ <b>مهم:</b> أرسل المجموع الإجمالي أعلاه.\n"
        "إذا أرسلت المبلغ الأساسي فقط، فسيتم اقتطاع رسوم الخدمة منه.\n\n"
        "⏱ المدة المتوقعة: 15 دقيقة - 24 ساعة"
    )

    await callback.message.edit_text(summary, parse_mode="HTML")
    await callback.message.answer(
        locale_service.get("confirm_order", lang)
        if locale_service.get("confirm_order", lang)
        else "✅ تأكيد وإرسال الطلب",
        reply_markup=order_confirmation_keyboard(lang),
    )
    await state.set_state(OrderStates.waiting_confirmation)
    await callback.answer()
