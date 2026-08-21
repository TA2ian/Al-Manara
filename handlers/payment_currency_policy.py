"""Authoritative payment-currency selection for the customer order flow."""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import order_confirmation_keyboard
from locale import locale_alias
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


@router.callback_query(OrderStates.waiting_currency, F.data.startswith("currency_"))
async def select_payment_currency(callback: CallbackQuery, state: FSMContext):
    """Calculate and display the immutable quote after currency selection."""
    # Acknowledge immediately so Telegram does not leave the button spinner active.
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
        exchange = ExchangeService(pool)
        calculation = await exchange.calculate_order(amount, currency)
        await state.update_data(payment_currency=calculation["payment_currency"], calculation=calculation)

        network_display = {
            "TRC20": "🔷 TRC20 (TRX)",
            "BEP20": "🟡 BEP20 (BNB)",
        }.get(network, network)

        new_syr_line = ""
        new_syr_fee_line = ""
        new_syr_total_line = ""
        if calculation["payment_currency"] == "NEW.SYP":
            new_syr_line = f"🇸🇾 بما يعادل: <b>{calculation['base_amount']:,.2f} ل.ج.س</b> (ليرة سورية جديدة)\n"
            new_syr_fee_line = f"🇸🇾 رسوم الخدمة: <b>{calculation['fee_amount']:,.2f} ل.ج.س</b>\n"
            new_syr_total_line = f"🇸🇾 الإجمالي بل.ج.س: <b>{calculation['total_amount']:,.2f} ل.ج.س</b>\n"

        summary = locale_service.get(
            "order_summary",
            lang,
            order_number="PENDING",
            amount_usdt=data["amount_usdt"],
            network=network_display,
            wallet=wallet,
            currency=calculation["payment_currency"],
            rate=calculation["exchange_rate"],
            base_amount=calculation["base_amount"],
            fee_percent=calculation["fee_percent"],
            fee_amount=calculation["fee_amount"],
            total=calculation["total_amount"],
            new_syr_line=new_syr_line,
            new_syr_fee_line=new_syr_fee_line,
            new_syr_total_line=new_syr_total_line,
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
