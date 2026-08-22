"""Customer and admin notification service."""
import logging
from decimal import Decimal, InvalidOperation

from aiogram import Bot

logger = logging.getLogger(__name__)


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


class NotificationService:
    """Send authoritative order/payment notifications."""

    def __init__(self, bot: Bot, admin_ids: list):
        self._bot = bot
        self._admin_ids = admin_ids

    async def notify_admins(self, message: str, parse_mode: str = "HTML"):
        for admin_id in self._admin_ids:
            try:
                await self._bot.send_message(admin_id, message, parse_mode=parse_mode)
            except Exception as exc:
                logger.error("Failed to notify admin %s: %s", admin_id, exc)

    async def notify_user(self, user_id: int, message: str, parse_mode: str = "HTML"):
        try:
            await self._bot.send_message(user_id, message, parse_mode=parse_mode)
        except Exception as exc:
            logger.error("Failed to notify user %s: %s", user_id, exc)
            raise

    async def notify_new_order(self, order: dict):
        text = (
            "📦 <b>طلب جديد!</b>\n\n"
            f"📋 الرقم: #{order['order_number']}\n"
            f"👤 العميل: {order.get('username', 'N/A')}\n"
            f"💰 المبلغ: {_format_usdt(order['amount_usdt'])} USDT\n"
            f"🌐 الشبكة: {order['network']}\n"
            f"💱 العملة: {order['payment_currency']}"
        )
        await self.notify_admins(text)

    async def notify_order_approved(self, user_id: int, order: dict, lang: str = "ar"):
        """Send the complete immutable payment snapshot after approval.

        This deliberately does not depend on a locale key: missing translation
        keys must never reduce a financial payment message to a key name.
        """
        from config import Config
        from services.exchange_service import ExchangeService

        currency = "NEW.SYP" if order.get("payment_currency") in ("SYP", "NEW.SYP") else "USD"
        account = (order.get("payment_account_snapshot") or "").strip()
        qr_photo_id = (order.get("payment_qr_photo_id") or "").strip()
        amount = _format_money(order.get("total_amount"))
        order_number = order.get("order_number", "N/A")
        timeout = Config.PAYMENT_TIMEOUT
        name = Config.get_shamcash_name().strip() or "ShamCash"

        # An approved order must always have the immutable payment snapshot.
        # Never substitute a live/current payment method here.
        if not account or not qr_photo_id:
            logger.error(
                "Incomplete payment snapshot for approved order %s: account=%r qr=%r",
                order_number, bool(account), bool(qr_photo_id),
            )
            await self.notify_user(
                user_id,
                (
                    f"⚠️ <b>تعذر إرسال بيانات الدفع للطلب #{order_number}</b>\n\n"
                    "بيانات الدفع المثبتة لهذا الطلب غير مكتملة. لا ترسل أي مبلغ، ويرجى مراجعة الإدارة."
                    if lang == "ar" else
                    f"⚠️ <b>Payment details unavailable for order #{order_number}</b>\n\n"
                    "The immutable payment details for this order are incomplete. Do not send funds; please contact administration."
                ),
            )
            return False

        old_syp_line = ""
        if currency == "NEW.SYP":
            old_syp_amount = order.get("old_syp_total")
            if old_syp_amount is None:
                old_syp_amount = ExchangeService.old_syp_equivalent(order.get("total_amount"))
            old_syp_line = (
                f"\nℹ️ يعادل <b>{_format_money(old_syp_amount)}</b> ليرة سورية قديمة"
                if lang == "ar" else
                f"\nℹ️ Equivalent to <b>{_format_money(old_syp_amount)}</b> legacy Syrian pounds"
            )

        if lang == "ar":
            text = (
                f"🔔 <b>تمت الموافقة على طلبك #{order_number}</b>\n\n"
                "💳 <b>بيانات الدفع الرسمية</b>\n"
                f"🏦 الجهة: <b>{name}</b>\n"
                f"💱 عملة الدفع: <b>{currency}</b>\n"
                f"💰 المبلغ المطلوب: <b>{amount} {currency}</b>\n"
                f"📱 حساب شام كاش: <code>{account}</code>\n"
                f"⏱ مهلة الدفع: <b>{timeout} دقيقة</b>"
                f"{old_syp_line}\n\n"
                "⚠️ <b>لا ترسل أي مبلغ قبل التأكد من أن بيانات الدفع مطابقة لهذه الرسالة.</b>\n"
                "بعد الدفع، أرسل إثبات العملية من زر رفع الإيصال الذي سيظهر لك."
            )
        else:
            text = (
                f"🔔 <b>Your order #{order_number} has been approved</b>\n\n"
                "💳 <b>Official Payment Details</b>\n"
                f"🏦 Provider: <b>{name}</b>\n"
                f"💱 Payment currency: <b>{currency}</b>\n"
                f"💰 Amount due: <b>{amount} {currency}</b>\n"
                f"📱 ShamCash account: <code>{account}</code>\n"
                f"⏱ Payment deadline: <b>{timeout} minutes</b>"
                f"{old_syp_line}\n\n"
                "⚠️ <b>Do not send funds until these payment details match this message.</b>\n"
                "After payment, use the receipt-upload button to submit your proof."
            )

        # The text message is mandatory and contains the account + exact amount.
        await self.notify_user(user_id, text)

        # QR is supplemental. If Telegram rejects the photo, the account details
        # have already reached the customer and the failure is logged.
        caption = (
            f"💳 <b>QR الدفع — {name}</b>\n"
            f"📦 الطلب: <b>#{order_number}</b>\n"
            f"💰 المبلغ: <b>{amount} {currency}</b>\n"
            f"📱 الحساب: <code>{account}</code>"
        ) if lang == "ar" else (
            f"💳 <b>Payment QR — {name}</b>\n"
            f"📦 Order: <b>#{order_number}</b>\n"
            f"💰 Amount: <b>{amount} {currency}</b>\n"
            f"📱 Account: <code>{account}</code>"
        )
        try:
            await self._bot.send_photo(
                user_id,
                qr_photo_id,
                caption=caption,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.exception("Failed to send payment QR for order %s: %s", order_number, exc)

        return True
