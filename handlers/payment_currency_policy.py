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


def _money(value, currency: str) -> str:
    """Format customer payment amounts with exactly two decimals."""
    return f"{Decimal(str(value)):,.2f}"


def _usdt(value) -> str:
    """Format customer-facing USDT with exactly three decimals."""
    return f"{Decimal(str(value)):,.3f}"


def _rate(value) -> str:
    """Format NEW.SYP exchange rates with exactly two decimals."""
    return f"{Decimal(str(value)):,.2f}"


def _build_arabic_summary(data: dict, calculation: dict, network_display: str) -> str:
    """Build the order summary only; payment destination is shown after approval."""
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
        rate_block = (
            "──── 💱 سعر الصرف ────\n"
            f"🔄 <b>1 USD = {_rate(rate)} NEW.SYP</b>\n"
        )
    else:
        payment_currency = "🇺🇸 الدولار الأمريكي (USD)"
        unit = "USD"
        rate_block = ""

    return (
        "📋 <b>ملخص طلبك #PENDING</b>\n\n"
        "──── 💳 معلومات USDT ────\n"
        f"💰 المبلغ المطلوب: <b>{_usdt(amount_usdt)} USDT</b>\n"
        f"🌐 الشبكة: {network_display}\n"
        f"📍 العنوان: <code>{data['wallet']}</code>\n\n"
        f"{rate_block}"
        f"💳 عملة الدفع: <b>{payment_currency}</b>\n\n"
        "──── 💵 المبلغ الأساسي ────\n"
        f"💵 <b>{_money(base, unit)} {unit}</b>\n\n"
        "──── 💰 رسوم الخدمة ────\n"
        f"📊 النسبة: <b>{Decimal(str(fee_pct)):,.2f}%</b>\n"
        f"💵 قيمة الرسوم: <b>{_money(fee, unit)} {unit}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💸 <b>الإجمالي المستحق:</b>\n\n"
        f"<b>💰 {_money(total, unit)} {unit}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "ℹ️ بعد تأكيد الطلب وموافقة الإدارة، ستصلك رسالة منفصلة تتضمن تعليمات الدفع، والمبلغ المطلوب تحويله، وحساب ShamCash ورمز QR الخاص بالدفع.\n\n"
        "⏱ المدة المتوقعة: 15 دقيقة - 24 ساعة"
    )


def _build_english_summary(data: dict, calculation: dict, network_display: str) -> str:
    """Keep the English path consistent with the authoritative quote."""
    currency = calculation["payment_currency"]
    base = calculation["base_amount"]
    fee_pct = calculation["fee_percent"]
    fee = calculation["fee_amount"]
    total = calculation["total_amount"]
    amount_usdt = data["amount_usdt"]
    unit = "NEW.SYP" if currency == "NEW.SYP" else "USD"

    if currency == "NEW.SYP":
        rate_block = f"──── 💱 Exchange Rate ────\n🔄 <b>1 USD = {_rate(calculation['exchange_rate'])} NEW.SYP</b>\n"
    else:
        rate_block = ""

    return (
        "📋 <b>Order Summary #PENDING</b>\n\n"
        "──── 💳 USDT Details ────\n"
        f"💰 Requested: <b>{_usdt(amount_usdt)} USDT</b>\n"
        f"🌐 Network: {network_display}\n"
        f"📍 Address: <code>{data['wallet']}</code>\n\n"
        f"{rate_block}"
        f"💳 Payment currency: <b>{unit}</b>\n\n"
        "──── 💵 Base Amount ────\n"
        f"💵 <b>{_money(base, unit)} {unit}</b>\n\n"
        "──── 💰 Service Fee ────\n"
        f"📊 Rate: <b>{Decimal(str(fee_pct)):,.2f}%</b>\n"
        f"💵 Fee: <b>{_money(fee, unit)} {unit}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💸 <b>Total Due:</b>\n\n"
        f"<b>💰 {_money(total, unit)} {unit}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "ℹ️ After you confirm the order and it is approved, you will receive a separate payment message with the amount to transfer, the ShamCash account, and its payment QR code.\n\n"
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
        summary = (
            _build_arabic_summary(data_for_summary, calculation, network_display)
            if lang == "ar"
            else _build_english_summary(data_for_summary, calculation, network_display)
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
