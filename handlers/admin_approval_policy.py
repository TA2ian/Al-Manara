"""Authoritative order-approval notification policy."""
import asyncio
import html
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import receipt_upload_keyboard, admin_menu_keyboard
from services.notification_service import NotificationService
from services.order_state_service import InvalidOrderTransition, rollback_order, transition_order

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _format_usdt(value) -> str:
    try:
        return f"{Decimal(str(value)):,.3f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.000"


def _format_money(value) -> str:
    try:
        return f"{Decimal(str(value)):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


@router.callback_query(F.data.startswith("admin_approve_"))
async def approve_order_authoritative(callback: CallbackQuery, state: FSMContext):
    """Approve an order only when the complete payment destination can be delivered."""
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

        account = (order["payment_account_snapshot"] or "").strip()
        qr_photo_id = (order["payment_qr_photo_id"] or "").strip()
        if not account or not qr_photo_id:
            await callback.answer("⚠️ بيانات ShamCash لهذه العملة غير مكتملة. ثبّت الحساب وQR أولاً.", show_alert=True)
            await callback.message.answer(
                "⚠️ <b>لا يمكن اعتماد الطلب بعد.</b>\n\n"
                "بيانات الدفع الخاصة بالعملة المختارة غير مكتملة. يجب على الأدمن تثبيت حساب ShamCash وQR الخاصين به من <b>وسائل الدفع</b> ثم إعادة المحاولة.",
                parse_mode="HTML",
            )
            return

        deadline = datetime.now() + timedelta(minutes=Config.PAYMENT_TIMEOUT)
        try:
            order = await transition_order(
                conn,
                order_id,
                "waiting_payment",
                admin_id=callback.from_user.id,
                updates={"approved_at": datetime.now(), "payment_deadline": deadline},
            )
        except InvalidOrderTransition:
            await callback.answer("الطلب لم يعد بانتظار الموافقة", show_alert=True)
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
                await rollback_order(
                    conn,
                    order_id,
                    "pending",
                    admin_id=callback.from_user.id,
                    updates={"approved_at": None, "payment_deadline": None},
                )
            except InvalidOrderTransition:
                logger.exception("Failed to rollback approval for order %s", order_id)
        try:
            await bot.send_message(
                user_id,
                (
                    f"⚠️ تعذر إرسال بيانات الدفع للطلب #{order['order_number']} كاملة. <b>لا ترسل أي مبلغ حالياً.</b> ستتم إعادة المحاولة بعد تصحيح بيانات الدفع."
                    if lang == "ar" else
                    f"⚠️ The complete payment details for order #{order['order_number']} could not be delivered. <b>Do not send any funds yet.</b> We will retry after the payment details are corrected."
                ),
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to send payment delivery failure notice for %s", order_id)
        await callback.answer(
            "⚠️ تعذر إرسال بيانات الدفع كاملة. لم يتم تثبيت الموافقة." if lang == "ar" else
            "⚠️ Complete payment details could not be delivered. Approval was not finalized.",
            show_alert=True,
        )
        return

    try:
        upload_text = (
            f"📎 <b>بعد إتمام الدفع للطلب #{order['order_number']}، أرسل إثبات العملية.</b>\n\n"
            "يمكنك إرسال ملف الإثبات الذي تصدّره من شام كاش مباشرة، أو صورة إذا كانت متاحة.\n"
            "سيتم إرسال الإثبات للمراجعة قبل تأكيد الدفع."
        ) if lang == "ar" else (
            f"📎 <b>After completing payment for order #{order['order_number']}, send your proof.</b>\n\n"
            "You can send the proof file exported from ShamCash directly, or an image if available.\n"
            "The proof will be reviewed before payment is confirmed."
        )
        await bot.send_message(user_id, upload_text, parse_mode="HTML", reply_markup=receipt_upload_keyboard(order_id, lang))
    except Exception:
        logger.exception("Receipt prompt delivery failed for %s", order_id)

    try:
        admin_update_text = (
            f"💳 <b>تمت الموافقة على الطلب</b>\n\n"
            f"📦 #{html.escape(order['order_number'])}\n"
            f"👤 {html.escape(order['full_name'] or 'N/A')}\n"
            f"🆔 <code>{user_id}</code>\n"
            f"💰 {_format_usdt(order['amount_usdt'])} USDT\n"
            f"🌐 {order['network']}\n"
            f"💵 الإجمالي: {_format_money(order['total_amount'])} {order['payment_currency']}\n"
            f"⏱ المهلة: {Config.PAYMENT_TIMEOUT} دقيقة\n\n"
            "📎 بانتظار إثبات دفع العميل..."
        )
        await asyncio.gather(*[
            bot.send_message(admin_id, admin_update_text, parse_mode="HTML")
            for admin_id in Config.ADMIN_IDS
        ], return_exceptions=True)
    except Exception:
        logger.exception("Admin approval update failed for %s", order_id)

    await state.clear()
    await callback.answer("✅ تمت الموافقة!")
    await callback.message.edit_text(
        f"✅ تمت الموافقة على طلب #{order['order_number']}\n\n📎 تم إرسال بيانات الدفع وتعليمات رفع إثبات الدفع للعميل.",
        parse_mode="HTML",
    )
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
