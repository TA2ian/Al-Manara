"""Customer and admin notification service."""
import logging

from aiogram import Bot

from services.formatters import money, percent, usdt
from services.operational_policy_service import OperationalPolicyService

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

    async def notify_feedback(self, user: dict, text: str, attachment_type: str | None = None, attachment_file_id: str | None = None):
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
        """Deliver immutable payment details and the configured payment deadline duration.

        Customer-facing deadline UX intentionally exposes only the configured processing
        duration; server-side timestamps remain authoritative and are never taken from
        client-supplied time or location data.
        """
        recipient = (order.get("payment_recipient_name_snapshot") or "").strip()
        address = (order.get("payment_account_snapshot") or "").strip()
        qr_photo_id = (order.get("payment_qr_photo_id") or "").strip()
        order_number = order.get("order_number", "N/A")
        currency = "NEW.SYP" if order.get("payment_currency") in ("SYP", "NEW.SYP") else "USD"
        amount = money(order.get("total_amount"))
        fee_percent = percent(order.get("fee_percent"))
        fee_amount = money(order.get("fee_amount"))
        deadline_minutes = await OperationalPolicyService.get_payment_timeout_minutes()

        if not recipient or not address or not qr_photo_id:
            logger.error(
                "Incomplete payment snapshot for approved order %s: recipient=%r address=%r qr=%r",
                order_number, bool(recipient), bool(address), bool(qr_photo_id),
            )
            try:
                await self.notify_user(
                    user_id,
                    f"⚠️ <b>تعذر تجهيز بيانات الدفع للطلب #{order_number}</b>\n\nبيانات الدفع المثبتة لهذا الطلب غير مكتملة. <b>لا ترسل أي مبلغ.</b> يرجى مراجعة الإدارة."
                    if lang == "ar" else
                    f"⚠️ <b>Payment details unavailable for order #{order_number}</b>\n\nThe immutable payment details for this order are incomplete. <b>Do not send funds.</b> Please contact administration.",
                )
            except Exception:
                logger.exception("Failed to send incomplete-payment warning for %s", order_number)
            return False

        old_syp_line = ""
        if currency == "NEW.SYP":
            old_syp_amount = order.get("old_syp_total")
            if old_syp_amount is not None:
                old_syp_line = f"\nℹ️ يعادل <b>{money(old_syp_amount)}</b> ليرة سورية قديمة" if lang == "ar" else f"\nℹ️ Equivalent to <b>{money(old_syp_amount)}</b> legacy Syrian pounds"

        if lang == "ar":
            caption = (
                f"🔔 <b>بيانات الدفع الرسمية · الطلب #{order_number}</b>\n\n"
                "تم اعتماد الطلب. هذه هي بيانات الدفع المثبتة لهذا الطلب، ولا تستخدم أي بيانات من رسالة أخرى.\n\n"
                "💳 <b>الدفع إلى</b>\n"
                f"👤 المستلم: <b>{recipient}</b>\n"
                f"📍 العنوان/الحساب: <code>{address}</code>\n"
                f"💱 العملة: <b>{currency}</b>\n"
                f"💰 المبلغ المستحق: <b>{amount} {currency}</b>\n"
                f"🏷️ رسوم الخدمة: <b>{fee_amount} {currency}</b> ({fee_percent}%)"
                f"{old_syp_line}\n\n"
                "⏱️ <b>مهلة إتمام الدفع</b>\n"
                f"لديك <b>{deadline_minutes} دقيقة</b> من اعتماد الطلب لإتمام الدفع وإرسال الإثبات.\n\n"
                "🔎 <b>قبل التحويل</b>\n"
                "تحقق من اسم المستلم والعنوان مرة أخيرة. بعد إتمام الدفع ارفع الإثبات من داخل هذا الطلب."
            )
        else:
            caption = (
                f"🔔 <b>Official payment details · Order #{order_number}</b>\n\n"
                "Your order is approved. These are the payment details locked to this order; do not use details from another message.\n\n"
                "💳 <b>Pay to</b>\n"
                f"👤 Recipient: <b>{recipient}</b>\n"
                f"📍 Address/account: <code>{address}</code>\n"
                f"💱 Currency: <b>{currency}</b>\n"
                f"💰 Amount due: <b>{amount} {currency}</b>\n"
                f"🏷️ Service fee: <b>{fee_amount} {currency}</b> ({fee_percent}%)\n\n"
                "⏱️ <b>Payment deadline</b>\n"
                f"You have <b>{deadline_minutes} minutes</b> from order approval to complete the payment and upload the proof.\n\n"
                "🔎 <b>Before sending</b>\n"
                "Verify the recipient name and address one last time, then upload your proof from this order."
            )

        await self._bot.send_photo(user_id, qr_photo_id, caption=caption, parse_mode="HTML")
        return True
