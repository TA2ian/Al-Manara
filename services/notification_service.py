"""Customer and admin notification service."""
import logging

from aiogram import Bot

from services.formatters import money, usdt

logger = logging.getLogger(__name__)


class NotificationService:
    """Send authoritative order/payment and support notifications."""

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

    async def notify_feedback(
        self,
        user: dict,
        text: str,
        attachment_type: str | None = None,
        attachment_file_id: str | None = None,
    ):
        """Forward a validated support submission to every administrator."""
        user_id = user.get("telegram_id", "N/A")
        username = user.get("username") or "بدون"
        body = (
            "🆘 <b>رسالة دعم جديدة</b>\n\n"
            f"👤 المستخدم: @{username}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📝 الرسالة: {text or 'بدون نص'}"
        )
        for admin_id in self._admin_ids:
            try:
                await self._bot.send_message(admin_id, body, parse_mode="HTML")
                if attachment_file_id and attachment_type == "photo":
                    await self._bot.send_photo(admin_id, attachment_file_id, caption="📎 مرفق من العميل")
                elif attachment_file_id and attachment_type == "pdf":
                    await self._bot.send_document(admin_id, attachment_file_id, caption="📎 ملف PDF مرفق من العميل")
            except Exception as exc:
                logger.error("Failed to notify admin %s about feedback: %s", admin_id, exc)

    async def notify_new_order(self, order: dict):
        text = (
            "📦 <b>طلب جديد!</b>\n\n"
            f"📋 الرقم: #{order['order_number']}\n"
            f"👤 العميل: {order.get('username', 'N/A')}\n"
            f"💰 المبلغ: {usdt(order['amount_usdt'])} USDT\n"
            f"🌐 الشبكة: {order['network']}\n"
            f"💱 العملة: {order['payment_currency']}"
        )
        await self.notify_admins(text)

    async def notify_order_approved(self, user_id: int, order: dict, lang: str = "ar") -> bool:
        """Deliver the immutable payment snapshot as one mandatory QR message."""
        from config import Config
        from services.exchange_service import ExchangeService

        currency = "NEW.SYP" if order.get("payment_currency") in ("SYP", "NEW.SYP") else "USD"
        account = (order.get("payment_account_snapshot") or "").strip()
        qr_photo_id = (order.get("payment_qr_photo_id") or "").strip()
        amount = money(order.get("total_amount"))
        order_number = order.get("order_number", "N/A")
        timeout = Config.PAYMENT_TIMEOUT
        name = Config.get_shamcash_name().strip() or "ShamCash"

        if not account or not qr_photo_id:
            logger.error("Incomplete payment snapshot for approved order %s: account=%r qr=%r", order_number, bool(account), bool(qr_photo_id))
            try:
                await self.notify_user(user_id, (f"⚠️ <b>تعذر إرسال بيانات الدفع للطلب #{order_number}</b>\n\nبيانات الدفع المثبتة لهذا الطلب غير مكتملة. لا ترسل أي مبلغ، ويرجى مراجعة الإدارة." if lang == "ar" else f"⚠️ <b>Payment details unavailable for order #{order_number}</b>\n\nThe immutable payment details for this order are incomplete. Do not send funds; please contact administration."))
            except Exception:
                logger.exception("Failed to send incomplete-payment warning for %s", order_number)
            return False

        old_syp_line = ""
        if currency == "NEW.SYP":
            old_syp_amount = order.get("old_syp_total")
            if old_syp_amount is None:
                old_syp_amount = ExchangeService.old_syp_equivalent(order.get("total_amount"))
            old_syp_line = f"\nℹ️ يعادل <b>{money(old_syp_amount)}</b> ليرة سورية قديمة" if lang == "ar" else f"\nℹ️ Equivalent to <b>{money(old_syp_amount)}</b> legacy Syrian pounds"

        caption = (
            f"🔔 <b>تمت الموافقة على طلبك #{order_number}</b>\n\n"
            "💳 <b>بيانات الدفع الرسمية</b>\n"
            f"🏦 الجهة: <b>{name}</b>\n"
            f"💱 عملة الدفع: <b>{currency}</b>\n"
            f"💰 المبلغ المطلوب: <b>{amount} {currency}</b>\n"
            f"📱 حساب شام كاش: <code>{account}</code>\n"
            f"⏱ مهلة الدفع: <b>{timeout} دقيقة</b>{old_syp_line}\n\n"
            "⚠️ <b>لا ترسل أي مبلغ قبل التأكد من مطابقة هذه البيانات.</b>"
            if lang == "ar" else
            f"🔔 <b>Your order #{order_number} has been approved</b>\n\n"
            "💳 <b>Official Payment Details</b>\n"
            f"🏦 Provider: <b>{name}</b>\n"
            f"💱 Payment currency: <b>{currency}</b>\n"
            f"💰 Amount due: <b>{amount} {currency}</b>\n"
            f"📱 ShamCash account: <code>{account}</code>\n"
            f"⏱ Payment deadline: <b>{timeout} minutes</b>{old_syp_line}\n\n"
            "⚠️ <b>Do not send funds until these details match.</b>"
        )

        await self._bot.send_photo(user_id, qr_photo_id, caption=caption, parse_mode="HTML")
        try:
            await self.notify_user(user_id, "📎 بعد الدفع، أرسل إثبات العملية من زر رفع الإيصال الذي سيظهر لك." if lang == "ar" else "📎 After payment, use the receipt-upload button to submit your proof.")
        except Exception:
            logger.exception("Failed to send secondary receipt instruction for %s", order_number)
        return True
