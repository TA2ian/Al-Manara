"""Authoritative payment-currency selection for the customer order flow."""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database import get_pool
from keyboards.inline import order_confirmation_keyboard
from services.exchange_service import ExchangeService
from services.formatters import money, percent, rate, usdt
from states import OrderStates, WalletStates

logger = logging.getLogger(__name__)
router = Router()


async def _user_lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


def _build_arabic_summary(data: dict, calculation: dict, network_display: str) -> str:
    currency = calculation["payment_currency"]
    unit = "NEW.SYP" if currency == "NEW.SYP" else "USD"
    payment_currency = "🇸🇾 الليرة السورية الجديدة (NEW.SYP)" if unit == "NEW.SYP" else "🇺🇸 الدولار الأمريكي (USD)"
    rate_block = f"──── 💱 سعر الصرف ────\n🔄 <b>1 USD = {rate(calculation['exchange_rate'])} NEW.SYP</b>\n" if unit == "NEW.SYP" else ""
    return (
        "📋 <b>ملخص طلب الشراء</b>\n\n"
        "──── 💳 قيمة الطلب ────\n"
        f"💰 المبلغ الذي حددته: <b>{usdt(calculation['requested_amount_usdt'])} USDT</b>\n"
        f"💸 المبلغ الذي سيصلك: <b>{usdt(calculation['net_amount_usdt'])} USDT</b>\n"
        f"🌐 الشبكة: {network_display}\n"
        f"📍 عنوان الاستلام: <code>{data['wallet']}</code>\n\n"
        f"{rate_block}"
        f"💳 عملة الدفع: <b>{payment_currency}</b>\n\n"
        "──── 💵 الحساب ────\n"
        f"💵 قيمة الطلب قبل الرسوم: <b>{money(calculation['base_amount'])} {unit}</b>\n"
        f"📊 رسوم شبكة {calculation['network']} ({percent(calculation['fee_percent'])}%): <b>{money(calculation['fee_amount'])} {unit}</b>\n"
        f"💰 صافي USDT بعد الرسوم: <b>{usdt(calculation['net_amount_usdt'])} USDT</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💸 <b>المبلغ المطلوب دفعه:</b>\n\n"
        f"<b>💰 {money(calculation['total_amount'])} {unit}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "ℹ️ رسوم الخدمة تُخصم من المبلغ الذي حددته ولا تُضاف فوقه. راجع التفاصيل جيداً. عند التأكيد سيُرسل الطلب إلى الإدارة للموافقة. بعد الموافقة ستصلك بيانات الدفع الرسمية.\n\n"
        "⚠️ لا ترسل أي مبلغ قبل ظهور تعليمات الدفع الرسمية داخل البوت."
    )


def _build_english_summary(data: dict, calculation: dict, network_display: str) -> str:
    currency = calculation["payment_currency"]
    unit = "NEW.SYP" if currency == "NEW.SYP" else "USD"
    rate_block = f"──── 💱 Exchange Rate ────\n🔄 <b>1 USD = {rate(calculation['exchange_rate'])} NEW.SYP</b>\n" if unit == "NEW.SYP" else ""
    return (
        "📋 <b>Purchase Order Summary</b>\n\n"
        "──── 💳 Order Value ────\n"
        f"💰 Amount you entered: <b>{usdt(calculation['requested_amount_usdt'])} USDT</b>\n"
        f"💸 You will receive: <b>{usdt(calculation['net_amount_usdt'])} USDT</b>\n"
        f"🌐 Network: {network_display}\n"
        f"📍 Receiving address: <code>{data['wallet']}</code>\n\n"
        f"{rate_block}"
        f"💳 Payment currency: <b>{unit}</b>\n\n"
        "──── 💵 Calculation ────\n"
        f"💵 Order value before fee: <b>{money(calculation['base_amount'])} {unit}</b>\n"
        f"📊 {calculation['network']} network fee ({percent(calculation['fee_percent'])}%): <b>{money(calculation['fee_amount'])} {unit}</b>\n"
        f"💰 Net USDT after fee: <b>{usdt(calculation['net_amount_usdt'])} USDT</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💸 <b>Amount to pay:</b>\n\n"
        f"<b>💰 {money(calculation['total_amount'])} {unit}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "ℹ️ The service fee is deducted from the amount you entered; it is not added on top. Review the details carefully. When confirmed, the order will be sent to administration for approval. Official payment details will be issued after approval.\n\n"
        "⚠️ Do not send any money until the official payment instructions appear inside the bot."
    )


@router.callback_query(OrderStates.waiting_currency, F.data.startswith("currency_"))
async def select_payment_currency(callback: CallbackQuery, state: FSMContext):
    """Calculate a quote only for an enabled and complete ShamCash method."""
    await callback.answer()
    currency = callback.data.removeprefix("currency_")
    if currency == "SYP":
        currency = "NEW.SYP"
    lang = await _user_lang(callback.from_user.id)
    try:
        pool = await get_pool()
        data = await state.get_data()

        if data.get("wallet_qr_skipped") or not data.get("wallet_qr_photo_id"):
            wallet = data.get("wallet_address")
            network = data.get("network")
            if not wallet or not network:
                await callback.message.answer(
                    "❌ بيانات المحفظة غير مكتملة. أعد إضافة المحفظة قبل متابعة الطلب." if lang == "ar" else
                    "❌ Wallet data is incomplete. Register the wallet again before continuing."
                )
                return
            await state.update_data(return_to_order=True, wallet_qr_skipped=False)
            await state.set_state(WalletStates.waiting_qr)
            await callback.message.edit_text(
                "🔐 <b>يلزم QR للمحفظة قبل متابعة الطلب</b>\n\n"
                f"🌐 الشبكة: <b>{network}</b>\n📍 العنوان: <code>{wallet}</code>\n\n"
                "لأمان الطلب، لا يمكن إنشاء طلب شراء بدون QR مطابق محفوظ للمحفظة. أرسل صورة QR لنفس العنوان الآن."
                if lang == "ar" else
                "🔐 <b>Wallet QR is required before continuing</b>\n\n"
                f"🌐 Network: <b>{network}</b>\n📍 Address: <code>{wallet}</code>\n\n"
                "For order safety, a purchase order cannot be created without a matching stored wallet QR. Send the QR image for this address now.",
                parse_mode="HTML",
            )
            return

        async with pool.acquire() as conn:
            method = await conn.fetchrow(
                """SELECT code, account_identifier, qr_photo_id, enabled
                   FROM payment_methods
                   WHERE provider='ShamCash' AND currency=$1
                   ORDER BY id ASC LIMIT 1""",
                currency,
            )
        if not method or not method["enabled"] or not (method["account_identifier"] or "").strip() or not method["qr_photo_id"]:
            await callback.message.answer(
                "❌ وسيلة الدفع لهذه العملة غير متاحة حالياً. اختر عملة أخرى أو حاول لاحقاً."
                if lang == "ar" else
                "❌ Payment for this currency is currently unavailable. Choose another currency or try later."
            )
            return

        amount = data.get("amount_usdt") or data.get("order_amount_usdt")
        wallet = data.get("wallet_address")
        network = data.get("network")
        if amount is None or not wallet or not network:
            await callback.message.answer(
                "❌ بيانات الطلب غير مكتملة. أعد إنشاء الطلب من القائمة الرئيسية."
                if lang == "ar" else
                "❌ The order data is incomplete. Please start the order again from the main menu."
            )
            return

        if data.get("amount_usdt") is None:
            await state.update_data(amount_usdt=amount)

        calculation = await ExchangeService(pool).calculate_order(amount, currency, network=network)
        await state.update_data(
            payment_currency=calculation["payment_currency"],
            calculation=calculation,
            requested_amount_usdt=calculation["requested_amount_usdt"],
            net_amount_usdt=calculation["net_amount_usdt"],
        )
        network_display = {
            "TRC20": "🔷 TRC20 (TRON)",
            "BEP20": "🟡 BEP20 (BNB Chain)",
            "TON": "💎 TON",
            "ARB": "🔵 ARB (Arbitrum)",
            "SOLANA": "🟣 Solana",
            "ETH": "🔷 Ethereum (ETH)",
        }.get(network.upper(), network)
        summary_data = {"amount_usdt": amount, "wallet": wallet}
        summary = _build_arabic_summary(summary_data, calculation, network_display) if lang == "ar" else _build_english_summary(summary_data, calculation, network_display)
        await callback.message.edit_text(summary, reply_markup=order_confirmation_keyboard(lang), parse_mode="HTML")
        await state.set_state(OrderStates.waiting_confirmation)
    except Exception:
        logger.exception("Payment currency selection failed for user %s", callback.from_user.id)
        await state.set_state(OrderStates.waiting_currency)
        await callback.message.answer("❌ تعذر حساب السعر حالياً. لم يتم إنشاء أي طلب أو خصم أي مبلغ. حاول اختيار العملة مرة أخرى." if lang == "ar" else "❌ The quote could not be calculated right now. No order was created and no funds were charged. Please try the currency again.")
