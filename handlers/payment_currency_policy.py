"""Authoritative payment-currency selection for the customer order flow."""
import logging
from decimal import Decimal

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database import get_pool
from keyboards.inline import order_confirmation_keyboard
from services.exchange_service import ExchangeService
from services.locale_service import locale_service
from states import OrderStates

logger = logging.getLogger(__name__)
router = Router()


async def _user_lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


def _money(value) -> str:
    return f"{Decimal(str(value)):,.2f}"


def _build_arabic_summary(data: dict, calculation: dict, network_display: str) -> str:
    """Build an explicit financial summary with a clear amount-to-send hierarchy."""
    currency = calculation["payment_currency"]
    rate = calculation["exchange_rate"]
    base = calculation["base_amount"]
    fee_pct = calculation["fee_percent"]
    fee = calculation["fee_amount"]
    total = calculation["total_amount"]
    amount_usdt = data["amount_usdt"]

    if currency == "NEW.SYP":
        payment_currency = "🇸🇾 الليرة السورية الجديدة (NEW.SYP)"
        unit = "NEW.SYP"
    else:
        payment_currency = "🇺🇸 الدولار الأمريكي (USD)"
        unit = "USD"

    return (
        "📋 <b>ملخص طلبك #PENDING</b>\n\n"
        "──── 💳 معلومات USDT ────\n"
        f"💰 المبلغ المطلوب: <b>{_money(amount_usdt)} USDT</b>\n"
        f"🌐 الشبكة: {network_display}\n"
        f"📍 العنوان: <code>{data['wallet']}</code>\n\n"
        "──── 💱 سعر الصرف ────\n"
        "🇺🇸 <b>الدولار الأمريكي (USD): 1.00 USD</b>\n"
        f"🇸🇾 <b>الليرة السورية الجديدة (NEW.SYP): {_money(rate)} NEW.SYP</b>\n"
        f"🔄 <b>1 USD = {_money(rate)} NEW.SYP</b>\n\n"
        f"💳 عملة الدفع: <b>{payment_currency}</b>\n\n"
        "👇 <b>المبلغ الذي سيصل إلى محفظتك:</b>\n"
        f"<b>💰 {_money(amount_usdt)} USDT</b>\n\n"
        "──── 💵 المبلغ الأساسي ────\n"
        f"💵 <b>{_money(base)} {unit}</b>\n\n"
        "──── 💰 رسوم الخدمة ────\n"
        f"📊 النسبة: <b>{_money(fee_pct)}%</b>\n"
        f"💵 قيمة الرسوم: <b>{_money(fee)} {unit}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💸 <b>المجموع الإجمالي — المبلغ المطلوب إرساله:</b>\n"
        f"<b>💰 {_money(total)} {unit}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ <b>مهم:</b> أرسل المجموع الإجمالي أعلاه.\n"
        "إذا أرسلت المبلغ الأساسي فقط، فسيتم اقتطاع رسوم الخدمة منه.\n\n"
        "⏱ المدة المتوقعة: 15 دقيقة - 24 ساعة"
    )


def _build_english_summary(data: dict, calculation: dict, network_display: str) -> str:
    """Keep the English path consistent with the authoritative quote."""
    currency = calculation["payment_currency"]
    rate = calculation["exchange_rate"]
    base = calculation["base_amount"]
    fee_pct = calculation["fee_percent"]
    fee = calculation["fee_amount"]
    total = calculation["total_amount"]
    amount_usdt = data["amount_usdt"]
    unit = "NEW.SYP" if currency == "NEW.SYP" else "USD"

    return (
        "📋 <b>Order Summary #PENDING</b>\n\n"
        "──── 💳 USDT Details ────\n"
        f"💰 Requested: <b>{_money(amount_usdt)} USDT</b>\n"
        f"🌐 Network: {network_display}\n"
        f"📍 Address: <code>{data['wallet']}</code>\n\n"
        "──── 💱 Exchange Rate ────\n"
        "🇺🇸 <b>US Dollar (USD): 1.00 USD</b>\n"
        f"🇸🇾 <b>New Syrian Pound (NEW.SYP): {_money(rate)} NEW.SYP</b>\n"
        f"🔄 <b>1 USD = {_money(rate)} NEW.SYP</b>\n\n"
        f"💳 Payment currency: <b>{unit}</b>\n\n"
        "👇 <b>Amount that will arrive in your wallet:</b>\n"
        f"<b>💰 {_money(amount_usdt)} USDT</b>\n\n"
        "──── 💵 Base Amount ────\n"
        f"💵 <b>{_money(base)} {unit}</b>\n\n"
        "──── 💰 Service Fee ────\n"
        f"📊 Rate: <b>{_money(fee_pct)}%</b>\n"
        f"💵 Fee: <b>{_money(fee)} {unit}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💸 <b>Total — Amount to Send:</b>\n"
        f"<b>💰 {_money(total)} {unit}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ <b>Important:</b> Send the total amount shown above.\n"
        "If you send only the base amount, the service fee will be deducted from it.\n\n"
        "⏱ Expected duration: 15 minutes - 24 hours"
    )


@router.callback_query(OrderStates.waiting_currency, F.data.startswith("currency_"))
async def select_payment_currency(callback: CallbackQuery, state: FSMContext):
    """Calculate and display the immutable quote after currency selection."""
    await callback.answer()
    currency = callback.data.removeprefix("currency_")
    lang = await _user_lang(callback.from_user.id)

    try:
        data = await state.get_data()
        amount = data.get("amount_usdt")
        wallet = data.get("wallet_address")
        network = data.get("network")

        if amount is None or not wallet or not network:
            await callback.message.answer(
                "❌ بيانات الطلب غير مكتملة. أعد إنشاء الطلب من القائمة الرئيسية."
                if lang == "ar" else
                "❌ The order data is incomplete. Please start the order again from the main menu."
            )
            await state.clear()
            return

        pool = await get_pool()
        calculation = await ExchangeService(pool).calculate_order(amount, currency)
        await state.update_data(
            payment_currency=calculation["payment_currency"],
            calculation=calculation,
        )

        network_display = {
            "TRC20": "🔷 TRC20 (TRX)",
            "BEP20": "🟡 BEP20 (BNB)",
        }.get(network, network)

        data_for_summary = {
            "amount_usdt": amount,
            "wallet": wallet,
        }
        if lang == "ar":
            summary = _build_arabic_summary(
                data_for_summary,
                calculation,
                network_display,
            )
        else:
            summary = _build_english_summary(
                data_for_summary,
                calculation,
                network_display,
            )

        await callback.message.edit_text(summary, parse_mode="HTML")
        await callback.message.answer(
            locale_service.get("confirm_order", lang),
            reply_markup=order_confirmation_keyboard(lang),
        )
        await state.set_state(OrderStates.waiting_confirmation)

    except Exception:
        logger.exception("Payment currency selection failed for user %s", callback.from_user.id)
        await state.set_state(OrderStates.waiting_currency)
        await callback.message.answer(
            "❌ تعذر حساب السعر حالياً. لم يتم إنشاء أي طلب أو خصم أي مبلغ. حاول اختيار العملة مرة أخرى."
            if lang == "ar" else
            "❌ The quote could not be calculated right now. No order was created and no funds were charged. Please try the currency again."
        )
