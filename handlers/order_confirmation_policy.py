"""Authoritative customer order confirmation flow."""
import html
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import main_menu_inline, order_admin_keyboard, receipt_upload_keyboard
from middleware.rate_limit import rate_limiter as global_rate_limiter
from services.exchange_service import FIXED_SERVICE_FEE_USDT
from services.formatters import money, usdt
from services.locale_service import locale_service
from services.notification_service import NotificationService
from services.operational_policy_service import OperationalPolicyService
from services.order_invoice_service import render_order_invoice
from services.order_state_service import InvalidOrderTransition, rollback_order, transition_order
from services.settings_service import SettingsService
from services.time_service import utc_now_naive
from states import OrderStates

router = Router()
logger = logging.getLogger(__name__)


def _html(value: object) -> str:
    """Escape a dynamic value before placing it in Telegram HTML."""
    return html.escape(str(value), quote=True)


def _order_number() -> str:
    return f"ORD_{utc_now_naive().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6].upper()}"


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
        required = ("amount_usdt", "network", "wallet_address", "wallet_id", "wallet_qr_photo_id", "payment_currency", "calculation")
        missing = [key for key in required if data.get(key) is None]
        if missing:
            logger.warning("Order confirmation rejected for telegram_id=%s; missing FSM keys=%s", callback.from_user.id, missing)
            await callback.answer("❌ بيانات الطلب غير مكتملة. أعد إنشاء الطلب." if lang == "ar" else "❌ The order data is incomplete. Please start the order again.", show_alert=True)
            await state.clear()
            return

        auto_approved = False
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id, language, terms_accepted, is_blocked, is_verified, full_name, username, shamcash_account FROM users WHERE telegram_id = $1", callback.from_user.id)
            if not user:
                await callback.answer("❌ يرجى بدء البوت أولاً: /start", show_alert=True)
                await state.clear()
                return
            lang = user["language"] or "ar"
            if not user["terms_accepted"] or user["is_blocked"] or not user["is_verified"]:
                await callback.answer("❌ لا يمكن إرسال الطلب قبل اكتمال متطلبات الحساب." if lang == "ar" else "❌ Your account requirements are not complete.", show_alert=True)
                return
            if not (user["full_name"] or "").strip() or not (user["shamcash_account"] or "").strip():
                await callback.answer("❌ بيانات حسابك غير مكتملة. أعد التحقق من الاسم وحساب ShamCash قبل إنشاء الطلب." if lang == "ar" else "❌ Your verified name or ShamCash account is incomplete. Please verify your account again before creating an order.", show_alert=True)
                return

            await conn.execute("SELECT pg_advisory_xact_lock($1)", int(user["id"]))
            active = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM orders WHERE user_id = $1 AND status IN ('pending','waiting_payment','receipt_received','payment_confirmed'))", user["id"])
            if active:
                await callback.answer("⚠️ لديك طلب نشط بالفعل. افتح «طلباتي»." if lang == "ar" else "⚠️ You already have an active order. Open Orders.", show_alert=True)
                await state.clear()
                return

            wallet = await conn.fetchrow("""SELECT id, address, network, qr_photo_id, verification_status
                FROM saved_addresses WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
                AND verification_status = 'verified' AND qr_photo_id IS NOT NULL""", data["wallet_id"], user["id"])
            if not wallet:
                await callback.answer("❌ المحفظة المحددة لم تعد موثقة أو لا تحتوي على QR محفوظ. اختر محفظة موثقة أخرى." if lang == "ar" else "❌ The selected wallet is no longer verified or has no stored QR. Choose another verified wallet.", show_alert=True)
                await state.clear()
                return

            if wallet["address"].strip().lower() != str(data["wallet_address"]).strip().lower() or wallet["network"] != data["network"] or wallet["qr_photo_id"] != data["wallet_qr_photo_id"]:
                logger.warning("Wallet FSM/DB mismatch for telegram_id=%s wallet_id=%s", callback.from_user.id, data["wallet_id"])
                await callback.answer("❌ تغيرت بيانات المحفظة أثناء الطلب. اختر المحفظة مرة أخرى." if lang == "ar" else "❌ The wallet data changed during this order. Please select the wallet again.", show_alert=True)
                await state.clear()
                return

            currency = "NEW.SYP" if data["payment_currency"] == "SYP" else data["payment_currency"]
            if currency not in ("USD", "NEW.SYP"):
                await callback.answer("❌ عملة الدفع غير صالحة." if lang == "ar" else "❌ Invalid payment currency.", show_alert=True)
                return

            payment = await conn.fetchrow("""SELECT code, account_identifier, qr_photo_id, recipient_name FROM payment_methods
                WHERE provider = 'ShamCash' AND currency = $1 AND code IN ('shamcash_usd', 'shamcash_new_syp')
                AND enabled = TRUE AND NULLIF(BTRIM(account_identifier), '') IS NOT NULL AND qr_photo_id IS NOT NULL
                AND NULLIF(BTRIM(recipient_name), '') IS NOT NULL
                ORDER BY id ASC LIMIT 1""", currency)
            if not payment:
                await callback.answer("❌ الدفع بهذه العملة غير متاح حالياً. يرجى المحاولة لاحقاً." if lang == "ar" else "❌ Payment for this currency is temporarily unavailable. Please try again later.", show_alert=True)
                return

            calculation = data["calculation"]
            requested_amount = calculation.get("requested_amount_usdt", data["amount_usdt"])
            net_amount = calculation.get("net_amount_usdt", data["amount_usdt"])
            order_number = _order_number()
            row = await conn.fetchrow("""INSERT INTO orders (order_number, user_id, network, requested_amount_usdt, amount_usdt, exchange_rate,
                payment_currency, base_amount, fee_percent, fee_amount, total_amount, wallet_address, wallet_qr_photo_id,
                payment_method_code, payment_account_snapshot, payment_qr_photo_id, payment_recipient_name_snapshot, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,'pending') RETURNING id""",
                order_number, user["id"], wallet["network"], requested_amount, net_amount, calculation["exchange_rate"], currency,
                calculation["base_amount"], Decimal("0"), calculation["fee_amount"], calculation["total_amount"],
                wallet["address"], wallet["qr_photo_id"], payment["code"], payment["account_identifier"], payment["qr_photo_id"], payment["recipient_name"])
            order_id = row["id"]
            completed_count = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE user_id = $1 AND status = 'completed'", user["id"])
            auto_approved = bool(await SettingsService.get_bool("auto_approve", False) and completed_count >= 3)
            if auto_approved:
                now_utc = utc_now_naive()
                deadline = now_utc + timedelta(minutes=await OperationalPolicyService.get_payment_timeout_minutes())
                try:
                    await transition_order(conn, order_id, "waiting_payment", updates={"approved_at": now_utc, "payment_deadline": deadline})
                except InvalidOrderTransition:
                    logger.exception("Trusted-customer auto approval transition failed for order %s", order_id)
                    auto_approved = False
            customer = await conn.fetchrow("SELECT full_name, username, shamcash_account FROM users WHERE id = $1", user["id"])

        from aiogram import Bot
        bot = Bot(token=Config.BOT_TOKEN)
        customer_name = (customer["full_name"] if customer else None) or user["full_name"] or "N/A"
        username = (customer["username"] if customer else None) or user["username"] or "N/A"
        customer_shamcash = (customer["shamcash_account"] if customer else None) or user["shamcash_account"] or "N/A"
        if auto_approved:
            async with pool.acquire() as conn:
                order = await conn.fetchrow("SELECT o.*, u.telegram_id, u.language, u.full_name, u.username, u.shamcash_account FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1", order_id)
            try:
                delivered = await NotificationService(bot, Config.ADMIN_IDS).notify_order_approved(callback.from_user.id, dict(order), lang=lang)
                if not delivered:
                    raise RuntimeError("auto_approval_payment_delivery_failed")
            except Exception:
                logger.exception("Trusted-customer auto approval delivery failed for order %s", order_id)
                async with pool.acquire() as conn:
                    try:
                        await rollback_order(conn, order_id, "pending", updates={"approved_at": None, "payment_deadline": None})
                    except InvalidOrderTransition:
                        logger.exception("Failed to rollback auto approval for order %s", order_id)
                auto_approved = False

        admin_status = "waiting_payment" if auto_approved else "pending"
        admin_text = (f"📦 <b>{'تم اعتماد طلب USDT تلقائياً' if auto_approved else 'طلب شراء USDT جديد'}</b>\n\n"
            f"📋 الرقم: #{_html(order_number)}\n👤 العميل: {_html(customer_name)}\n🆔 المعرف: <code>{_html(callback.from_user.id)}</code>\n"
            f"👤 المستخدم: @{_html(username)}\n🏦 ShamCash العميل: <code>{_html(customer_shamcash)}</code>\n"
            f"💰 المبلغ المحدد: {_html(usdt(requested_amount))} USDT\n💸 المبلغ المستحق للعميل: {_html(usdt(net_amount))} USDT\n"
            f"🌐 الشبكة: {_html(wallet['network'])}\n💱 عملة الدفع: {_html(currency)}\n"
            f"💵 المبلغ المدفوع: {_html(money(calculation['total_amount']))} {_html(currency)}\n"
            f"💰 رسوم الخدمة الثابتة: {_html(usdt(FIXED_SERVICE_FEE_USDT))} USDT ({_html(money(calculation['fee_amount']))} {_html(currency)})\n"
            f"📍 <b>عنوان الاستلام:</b> <code>{_html(wallet['address'])}</code>\n\n"
            + ("⭐ العميل موثوق (3 طلبات مكتملة أو أكثر). تم إرسال بيانات الدفع الرسمية إليه، والطلب الآن بانتظار إثبات الدفع." if auto_approved else "📝 يرجى مراجعة بيانات الطلب قبل الموافقة. ستصل للعميل تعليمات الدفع الرسمية بعد الموافقة."))
        for admin_id in Config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, reply_markup=order_admin_keyboard(order_id, admin_status), parse_mode="HTML")
            except Exception:
                logger.exception("Failed to notify admin for order %s", order_id)

        invoice = render_order_invoice(
            order_number=order_number,
            requested_amount_usdt_value=requested_amount,
            amount_usdt_value=net_amount,
            network=wallet["network"],
            wallet=wallet["address"],
            currency=currency,
            exchange_rate_value=calculation["exchange_rate"],
            base_amount_value=calculation["base_amount"],
            fee_percent_value=calculation["fee_percent"],
            fee_amount_value=calculation["fee_amount"],
            total_value=calculation["total_amount"],
            lang=lang,
        )
        await callback.message.edit_text(invoice, parse_mode="HTML")
        if auto_approved:
            status_message = await callback.message.answer("✅ تمت الموافقة تلقائياً لأن حسابك يحقق متطلبات العميل الموثوق. تم إرسال بيانات ShamCash الرسمية لك. أتمم الدفع ثم ارفع الإثبات." if lang == "ar" else "✅ Your order was automatically approved because your account meets the trusted-customer requirements. Official ShamCash payment details have been sent. Complete payment and upload the proof.", reply_markup=receipt_upload_keyboard(order_id, lang))
        else:
            status_message = await callback.message.answer("⏳ تم إنشاء الطلب وإرساله إلى الإدارة للمراجعة. لا ترسل أي مبلغ الآن؛ ستصلك بيانات الدفع الرسمية بعد الموافقة." if lang == "ar" else "⏳ Your order has been created and sent to administration for review. Do not send any payment yet; official payment details will appear after approval.")
        try:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE orders SET customer_status_message_id = $1 WHERE id = $2", status_message.message_id, order_id)
        except Exception:
            logger.exception("Failed to persist customer status message for order %s", order_id)
        await callback.message.answer(locale_service.get("main_menu", lang), reply_markup=main_menu_inline(lang))
        await state.clear()
        await callback.answer()
    except Exception:
        logger.exception("Order confirmation failed for telegram_id=%s", callback.from_user.id)
        await callback.answer("❌ تعذر إرسال الطلب حالياً. لم يتم اعتماد أي دفع. حاول مرة أخرى لاحقاً." if lang == "ar" else "❌ The order could not be submitted right now. No payment was accepted. Please try again later.", show_alert=True)
