"""Authoritative order-approval notification policy."""
import asyncio
import html
import logging
from datetime import timedelta

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import receipt_upload_keyboard
from services.formatters import money, usdt
from services.notification_service import NotificationService
from services.operational_policy_service import OperationalPolicyService
from services.order_state_service import InvalidOrderTransition, rollback_order, transition_order
from services.time_service import utc_now_naive

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _sync_customer_status_message(bot: Bot, order: dict, approved: bool) -> bool:
    """Replace the customer's stale approval-status message after delivery succeeds."""
    message_id = order.get("customer_status_message_id")
    user_id = order.get("telegram_id")
    if not message_id or not user_id:
        return False
    lang = order.get("language") or "ar"
    text = (
        f"✅ <b>تمت الموافقة على الطلب #{html.escape(order['order_number'])}</b>\n\n"
        "💳 تم إرسال بيانات الدفع الرسمية إلى هذه المحادثة.\n"
        "⏱ يرجى إتمام الدفع ضمن المهلة المحددة ثم رفع الإيصال.\n\n"
        "⚠️ لا تعتمد على أي بيانات دفع خارج رسالة الموافقة الرسمية."
        if lang == "ar" else
        f"✅ <b>Order #{html.escape(order['order_number'])} approved</b>\n\n"
        "💳 The official payment details have been sent to this chat.\n"
        "⏱ Complete the payment within the stated deadline, then upload the receipt.\n\n"
        "⚠️ Do not use payment details from outside the official approval message."
    ) if approved else (
        f"⏳ <b>الطلب #{html.escape(order['order_number'])} بانتظار موافقة الإدارة.</b>\n\nلا ترسل أي مبلغ قبل وصول تعليمات الدفع الرسمية."
        if lang == "ar" else
        f"⏳ <b>Order #{html.escape(order['order_number'])} is awaiting admin approval.</b>\n\nDo not send any funds before the official payment instructions arrive."
    )
    try:
        await bot.edit_message_text(chat_id=user_id, message_id=int(message_id), text=text, parse_mode="HTML")
        return True
    except Exception as exc:
        logger.warning("Could not synchronize customer status message for order %s: %s", order.get("order_number"), exc)
        return False


@router.callback_query(F.data.startswith("admin_approve_"))
async def approve_order_authoritative(callback: CallbackQuery, state: FSMContext):
    """Approve only after the complete immutable payment destination is deliverable."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_approve_", ""))
    pool = await get_pool()
    timeout_minutes = await OperationalPolicyService.get_payment_timeout_minutes()

    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.full_name, u.username, u.shamcash_account, u.telegram_id, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )
        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True)
            return
        if order["status"] != "pending":
            await callback.answer("الطلب لم يعد بانتظار الموافقة", show_alert=True)
            return

        account = (order["payment_account_snapshot"] or "").strip()
        recipient = (order["payment_recipient_name_snapshot"] or "").strip()
        qr_photo_id = (order["payment_qr_photo_id"] or "").strip()
        if not account or not recipient or not qr_photo_id:
            await callback.answer("⚠️ بيانات ShamCash لهذه العملة غير مكتملة. ثبّت الاسم والحساب وQR أولاً.", show_alert=True)
            await callback.message.answer(
                "⚠️ <b>لا يمكن اعتماد الطلب بعد.</b>\n\n"
                "بيانات الدفع الخاصة بالعملة المختارة غير مكتملة. يجب على الأدمن تثبيت اسم المستلم وحساب ShamCash وQR الخاصين به من <b>وسائل الدفع</b> ثم إعادة المحاولة.",
                parse_mode="HTML",
            )
            return

        now_utc = utc_now_naive()
        deadline = now_utc + timedelta(minutes=timeout_minutes)
        try:
            await transition_order(
                conn, order_id, "waiting_payment", admin_id=callback.from_user.id,
                updates={"approved_at": now_utc, "payment_deadline": deadline},
            )
        except InvalidOrderTransition:
            await callback.answer("الطلب لم يعد بانتظار الموافقة", show_alert=True)
            return

    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.full_name, u.username, u.shamcash_account, u.telegram_id, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )

    if not order:
        await callback.answer("❌ تعذر قراءة الطلب بعد الموافقة", show_alert=True)
        return

    user_id = order["telegram_id"]
    lang = order["language"] or "ar"
    bot = Bot(token=Config.BOT_TOKEN)

    try:
        notification = NotificationService(bot, Config.ADMIN_IDS)
        delivered = await notification.notify_order_approved(user_id, dict(order), lang=lang)
        if not delivered:
            raise RuntimeError("payment_details_delivery_failed")
    except Exception:
        logger.exception("Payment details delivery failed for order %s", order_id)
        async with pool.acquire() as conn:
            try:
                await rollback_order(conn, order_id, "pending", admin_id=callback.from_user.id, updates={"approved_at": None, "payment_deadline": None})
            except InvalidOrderTransition:
                logger.exception("Failed to rollback approval for order %s", order_id)
        try:
            await bot.send_message(
                user_id,
                (f"⚠️ تعذر إرسال بيانات الدفع للطلب #{order['order_number']} كاملة. <b>لا ترسل أي مبلغ حالياً.</b> ستتم إعادة المحاولة بعد تصحيح بيانات الدفع." if lang == "ar" else f"⚠️ The complete payment details for order #{order['order_number']} could not be delivered. <b>Do not send any funds yet.</b> We will retry after the payment details are corrected."),
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to send payment delivery failure notice for %s", order_id)
        await callback.answer("⚠️ تعذر إرسال بيانات الدفع كاملة. لم يتم تثبيت الموافقة." if lang == "ar" else "⚠️ Complete payment details could not be delivered. Approval was not finalized.", show_alert=True)
        return

    await _sync_customer_status_message(bot, dict(order), approved=True)

    upload_text = (
        f"📎 <b>بعد إتمام الدفع للطلب #{order['order_number']}، أرسل إثبات العملية.</b>\n\n"
        "يمكنك إرسال ملف الإثبات الذي تصدّره من شام كاش مباشرة، أو صورة إذا كانت متاحة.\n"
        "سيتم إرسال الإثبات للمراجعة قبل تأكيد الدفع."
    ) if lang == "ar" else (
        f"📎 <b>After completing payment for order #{order['order_number']}, send your proof.</b>\n\n"
        "You can send the proof file exported from ShamCash directly, or an image if available.\n"
        "The proof will be reviewed before payment is confirmed."
    )
    try:
        await bot.send_message(user_id, upload_text, parse_mode="HTML", reply_markup=receipt_upload_keyboard(order_id, lang))
    except Exception:
        logger.exception("Receipt prompt delivery failed for %s", order_id)

    admin_update_text = (
        f"💳 <b>تمت الموافقة على الطلب</b>\n\n"
        f"📦 #{html.escape(order['order_number'])}\n"
        f"👤 العميل: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 المستخدم: @{html.escape(order['username'] or 'N/A')}\n"
        f"🏦 ShamCash العميل: <code>{html.escape(order['shamcash_account'] or 'N/A')}</code>\n"
        f"💳 الدفع إلى: <b>{html.escape(order['payment_recipient_name_snapshot'] or 'N/A')}</b> — <code>{html.escape(order['payment_account_snapshot'] or 'N/A')}</code>\n"
        f"💰 {usdt(order['amount_usdt'])} USDT\n"
        f"🌐 {html.escape(order['network'] or '')}\n"
        f"💵 الإجمالي: {money(order['total_amount'])} {html.escape(order['payment_currency'])}\n"
        f"⏱ المهلة المحددة: <b>{timeout_minutes} دقيقة</b> من لحظة اعتماد الطلب\n\n"
        "📎 بانتظار إثبات دفع العميل..."
    )
    await asyncio.gather(*[bot.send_message(admin_id, admin_update_text, parse_mode="HTML") for admin_id in Config.ADMIN_IDS], return_exceptions=True)

    await state.clear()
    await callback.answer("✅ تمت الموافقة!")
    await callback.message.edit_text(
        f"✅ تمت الموافقة على طلب #{order['order_number']}\n\n📎 تم إرسال بيانات الدفع وتعليمات رفع إثبات الدفع للعميل.",
        parse_mode="HTML",
    )
