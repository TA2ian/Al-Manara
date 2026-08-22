"""Authoritative order-approval notification policy.

Ensures that once an admin approves an order, the customer always receives a
clear payment deadline and an explicit receipt-upload action, even if an
optional notification component fails.
"""
import asyncio
import html
import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from aiogram import Bot
from config import Config
from database import get_pool
from keyboards.inline import receipt_upload_keyboard, order_admin_keyboard, admin_menu_keyboard
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from services.notification_service import NotificationService

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.callback_query(F.data.startswith("admin_approve_"))
async def approve_order_authoritative(callback: CallbackQuery, state: FSMContext):
    """Approve an order and guarantee the customer gets receipt instructions."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_approve_", ""))
    pool = await get_pool()

    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.full_name, u.username, u.telegram_id, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )
        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True)
            return

        if order["status"] != "pending":
            await callback.answer("الطلب لم يعد بانتظار الموافقة", show_alert=True)
            return

        deadline = datetime.now() + timedelta(minutes=Config.PAYMENT_TIMEOUT)
        await conn.execute(
            "UPDATE orders SET status = 'waiting_payment', approved_at = NOW(), "
            "payment_deadline = $1 WHERE id = $2",
            deadline,
            order_id,
        )

        # Re-read the order so notification services receive the authoritative
        # waiting-payment state and deadline.
        order = await conn.fetchrow(
            "SELECT o.*, u.full_name, u.username, u.telegram_id, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )

    user_id = order["telegram_id"]
    lang = order["language"] or "ar"
    bot = Bot(token=Config.BOT_TOKEN)

    # Optional detailed notification. Its failure must never prevent the
    # mandatory receipt-upload prompt below.
    try:
        notification = NotificationService(bot, Config.ADMIN_IDS)
        await notification.notify_order_approved(
            user_id,
            dict(order),
            lang=lang,
        )
    except Exception as exc:
        logger.exception("Order approval notification failed for %s: %s", order_id, exc)

    # Mandatory customer-facing payment/receipt action.
    try:
        upload_text = (
            f"🔔 <b>تمت الموافقة على طلبك #{order['order_number']}</b>\n\n"
            f"💳 يمكنك الآن دفع المبلغ المطلوب.\n"
            f"⏱ <b>مهلة الدفع: {Config.PAYMENT_TIMEOUT} دقيقة</b>\n\n"
            "📎 <b>بعد إتمام الدفع، أرسل صورة إيصال التحويل من شام كاش عبر الزر أدناه.</b>\n"
            "يجب أن يكون الإيصال واضحاً ويظهر المبلغ والتاريخ وبيانات العملية."
        ) if lang == "ar" else (
            f"🔔 <b>Your order #{order['order_number']} has been approved</b>\n\n"
            "💳 You can now make the payment.\n"
            f"⏱ <b>Payment deadline: {Config.PAYMENT_TIMEOUT} minutes</b>\n\n"
            "📎 <b>After payment, send the ShamCash receipt using the button below.</b>\n"
            "Make sure the receipt clearly shows the amount, date, and transaction details."
        )
        await bot.send_message(
            user_id,
            upload_text,
            parse_mode="HTML",
            reply_markup=receipt_upload_keyboard(order_id, lang),
        )
    except Exception as exc:
        logger.exception("Mandatory receipt prompt failed for %s: %s", order_id, exc)
        # A second minimal attempt without the locale service or other helpers.
        try:
            await bot.send_message(
                user_id,
                f"📎 بعد الدفع، اضغط الزر أدناه وارفع إيصال الطلب #{order['order_number']}.",
                reply_markup=receipt_upload_keyboard(order_id, lang),
            )
        except Exception:
            logger.exception("Fallback receipt prompt failed for %s", order_id)

    # Admin-side state confirmation; failures here must not affect the customer.
    try:
        admin_update_text = (
            f"💳 <b>تمت الموافقة على الطلب</b>\n\n"
            f"📦 #{html.escape(order['order_number'])}\n"
            f"👤 {html.escape(order['full_name'] or 'N/A')}\n"
            f"🆔 <code>{user_id}</code>\n"
            f"💰 {order['amount_usdt']} USDT\n"
            f"🌐 {order['network']}\n"
            f"💵 الإجمالي: {order['total_amount']:.2f} {order['payment_currency']}\n"
            f"⏱ المهلة: {Config.PAYMENT_TIMEOUT} دقيقة\n\n"
            "📎 بانتظار إيصال العميل..."
        )
        await asyncio.gather(*[
            bot.send_message(admin_id, admin_update_text, parse_mode="HTML")
            for admin_id in Config.ADMIN_IDS
        ], return_exceptions=True)
    except Exception as exc:
        logger.exception("Admin approval update failed for %s: %s", order_id, exc)

    await state.clear()
    await callback.answer("✅ تمت الموافقة!")
    await callback.message.edit_text(
        f"✅ تمت الموافقة على طلب #{order['order_number']}\n\n"
        "📎 تم إرسال تعليمات الدفع ورفع الإيصال للعميل.",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "⚙️ <b>لوحة التحكم</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )
