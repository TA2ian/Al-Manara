"""Authoritative customer order confirmation flow.

This router owns confirm_order before the legacy order router. It validates the
FSM snapshot and the current payment destination, then creates one immutable
order snapshot and notifies admins.
"""
import logging
import uuid
from datetime import datetime

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import main_menu_inline, order_admin_keyboard
from middleware.rate_limit import rate_limiter as global_rate_limiter
from services.locale_service import locale_service
from states import OrderStates

router = Router()
logger = logging.getLogger(__name__)


def _order_number() -> str:
    return f"ORD_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6].upper()}"


@router.callback_query(OrderStates.waiting_confirmation, lambda c: c.data == "confirm_order")
async def confirm_order_authoritative(callback: CallbackQuery, state: FSMContext):
    allowed, _ = global_rate_limiter.check(callback.from_user.id, "order_confirm")
    if not allowed:
        await callback.answer()
        return

    lang = "ar"
    try:
        pool = await get_pool()
        data = await state.get_data()
        required = ("amount_usdt", "network", "wallet_address", "payment_currency", "calculation")
        if any(data.get(key) is None for key in required):
            await callback.answer(
                "❌ بيانات الطلب غير مكتملة. أعد إنشاء الطلب." if lang == "ar" else
                "❌ The order data is incomplete. Please start the order again.",
                show_alert=True,
            )
            await state.clear()
            return

        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id, language, terms_accepted, is_blocked, is_verified FROM users WHERE telegram_id = $1",
                callback.from_user.id,
            )
            if not user:
                await callback.answer("❌ يرجى بدء البوت أولاً: /start", show_alert=True)
                await state.clear()
                return
            lang = user["language"] or "ar"
            if not user["terms_accepted"] or user["is_blocked"] or not user["is_verified"]:
                await callback.answer(
                    "❌ لا يمكن إرسال الطلب قبل اكتمال متطلبات الحساب." if lang == "ar" else
                    "❌ Your account requirements are not complete.",
                    show_alert=True,
                )
                return

            active = await conn.fetchval(
                """SELECT EXISTS(
                    SELECT 1 FROM orders
                    WHERE user_id = $1
                      AND status IN ('pending','waiting_payment','receipt_received','payment_confirmed')
                )""",
                user["id"],
            )
            if active:
                await callback.answer(
                    "⚠️ لديك طلب نشط بالفعل. افتح «طلباتي»." if lang == "ar" else
                    "⚠️ You already have an active order. Open Orders.",
                    show_alert=True,
                )
                await state.clear()
                return

            currency = data["payment_currency"]
            if currency == "SYP":
                currency = "NEW.SYP"
            if currency not in ("USD", "NEW.SYP"):
                await callback.answer("❌ عملة الدفع غير صالحة." if lang == "ar" else "❌ Invalid payment currency.", show_alert=True)
                return

            payment = await conn.fetchrow(
                """SELECT code, account_identifier, qr_photo_id
                   FROM payment_methods
                   WHERE provider = 'ShamCash' AND currency = $1 AND enabled = TRUE
                     AND NULLIF(BTRIM(account_identifier), '') IS NOT NULL
                     AND qr_photo_id IS NOT NULL
                   ORDER BY id ASC LIMIT 1""",
                currency,
            )
            if not payment:
                await callback.answer(
                    "❌ الدفع بهذه العملة غير متاح حالياً. يرجى المحاولة لاحقاً." if lang == "ar" else
                    "❌ Payment for this currency is temporarily unavailable. Please try again later.",
                    show_alert=True,
                )
                return

            calculation = data["calculation"]
            order_number = _order_number()
            row = await conn.fetchrow(
                """INSERT INTO orders (
                    order_number, user_id, network, amount_usdt, exchange_rate,
                    payment_currency, base_amount, fee_percent, fee_amount,
                    total_amount, wallet_address, wallet_qr_photo_id,
                    payment_method_code, payment_account_snapshot, payment_qr_photo_id, status
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,'pending')
                RETURNING id""",
                order_number, user["id"], data["network"], data["amount_usdt"],
                calculation["exchange_rate"], currency, calculation["base_amount"],
                calculation["fee_percent"], calculation["fee_amount"], calculation["total_amount"],
                data["wallet_address"], data.get("wallet_qr_photo_id"), payment["code"],
                payment["account_identifier"], payment["qr_photo_id"],
            )
            order_id = row["id"]
            customer = await conn.fetchrow("SELECT full_name, username FROM users WHERE id = $1", user["id"])

        from aiogram import Bot
        bot = Bot(token=Config.BOT_TOKEN)
        customer_name = (customer["full_name"] if customer else None) or "N/A"
        username = (customer["username"] if customer else None) or "N/A"
        admin_text = (
            f"📦 <b>طلب شراء USDT جديد</b>\n\n"
            f"📋 الرقم: #{order_number}\n"
            f"👤 العميل: {customer_name}\n"
            f"🆔 المعرف: <code>{callback.from_user.id}</code>\n"
            f"👤 المستخدم: @{username}\n"
            f"💰 الكمية: {data['amount_usdt']:,.3f} USDT\n"
            f"🌐 الشبكة: {data['network']}\n"
            f"💱 عملة الدفع: {currency}\n"
            f"💵 الإجمالي: {calculation['total_amount']:,.2f} {currency}\n"
            f"📍 <b>عنوان الاستلام:</b> <code>{data['wallet_address']}</code>\n\n"
            "📝 يرجى مراجعة بيانات الطلب قبل الموافقة. ستصل للعميل تعليمات الدفع بعد الموافقة."
        )
        for admin_id in Config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id, admin_text,
                    reply_markup=order_admin_keyboard(order_id, "pending"),
                    parse_mode="HTML",
                )
            except Exception:
                logger.exception("Failed to notify admin for order %s", order_id)

        await callback.message.edit_text(
            locale_service.get("order_created", lang, order_number=order_number),
            parse_mode="HTML",
        )
        status_message = await callback.message.answer(
            "⏳ تم إرسال طلبك إلى الإدارة للمراجعة. لا ترسل أي مبلغ الآن؛ ستصلك تعليمات الدفع الرسمية بعد الموافقة."
            if lang == "ar" else
            "⏳ Your order has been sent to the administration for review. Do not send any payment yet; official payment instructions will appear after approval.",
        )
        # Persisting this UI pointer is a convenience feature. Failure here
        # must never turn a successfully-created order into a reported error.
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE orders SET customer_status_message_id = $1 WHERE id = $2",
                    status_message.message_id,
                    order_id,
                )
        except Exception:
            logger.exception("Failed to persist customer status message for order %s", order_id)

        await callback.message.answer(
            locale_service.get("main_menu", lang),
            reply_markup=main_menu_inline(lang),
        )
        await state.clear()
        await callback.answer()
    except Exception:
        logger.exception("Order confirmation failed for telegram_id=%s", callback.from_user.id)
        await callback.answer(
            "❌ تعذر إرسال الطلب حالياً. لم يتم اعتماد أي دفع. حاول مرة أخرى لاحقاً." if lang == "ar" else
            "❌ The order could not be submitted right now. No payment was accepted. Please try again later.",
            show_alert=True,
        )
