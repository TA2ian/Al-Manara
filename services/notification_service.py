"""Notification service."""
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
    """Send notifications to users and admins."""

    def __init__(self, bot: Bot, admin_ids: list):
        self._bot = bot
        self._admin_ids = admin_ids

    async def notify_admins(self, message: str, parse_mode: str = 'HTML'):
        """Send notification to all admins."""
        for admin_id in self._admin_ids:
            try:
                await self._bot.send_message(admin_id, message, parse_mode=parse_mode)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    async def notify_user(self, user_id: int, message: str, parse_mode: str = 'HTML'):
        """Send notification to user."""
        try:
            await self._bot.send_message(user_id, message, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")

    async def notify_new_order(self, order: dict):
        """Notify admins of new order."""
        text = f"""
📦 <b>طلب جديد!</b>

📋 الرقم: #{order['order_number']}
👤 العميل: {order.get('username', 'N/A')}
💰 المبلغ: {_format_usdt(order['amount_usdt'])} USDT
🌐 الشبكة: {order['network']}
💱 العملة: {order['payment_currency']}

[📋 عرض التفاصيل]
"""
        await self.notify_admins(text)

    async def notify_order_approved(self, user_id: int, order: dict, lang: str = 'ar'):
        """Notify user using the payment snapshot stored on the order."""
        from services.locale_service import locale_service
        from config import Config

        amount = _format_money(order['total_amount'])
        currency = 'NEW.SYP' if order['payment_currency'] == 'SYP' else order['payment_currency']
        account = order.get('payment_account_snapshot') or (
            Config.get_shamcash_syp() if currency == 'NEW.SYP' else Config.get_shamcash_usd()
        )
        name = Config.get_shamcash_name()
        qr_photo_id = order.get('payment_qr_photo_id')

        # The payment method is snapshotted on the order. This prevents a later
        # admin change from altering the payment instructions of an existing order.
        if not account or not qr_photo_id:
            # Compatibility fallback for orders created before snapshots existed.
            from database import get_pool
            pool = await get_pool()
            if pool:
                async with pool.acquire() as conn:
                    method = await conn.fetchrow(
                        """SELECT display_name, account_identifier, qr_photo_id
                           FROM payment_methods
                           WHERE provider = 'ShamCash' AND currency = $1 AND enabled = TRUE
                           ORDER BY id ASC LIMIT 1""",
                        currency,
                    )
                if method:
                    name = method['display_name'] or name
                    account = method['account_identifier'] or account
                    qr_photo_id = method['qr_photo_id'] or qr_photo_id

        text = locale_service.get(
            'order_approved',
            lang,
            order_number=order['order_number'],
            timeout=Config.PAYMENT_TIMEOUT,
            account=account,
            name=name,
            amount=amount,
            currency=currency,
        )

        await self.notify_user(user_id, text)

        # Legacy SYP is display-only. NEW.SYP is the actual payment currency.
        if currency == 'NEW.SYP':
            old_syp_amount = order.get('old_syp_total')
            if old_syp_amount is None:
                from services.exchange_service import ExchangeService
                old_syp_amount = ExchangeService.old_syp_equivalent(order['total_amount'])
            equivalent_line = (
                f"\nℹ️ يعادل <b>{_format_money(old_syp_amount)}</b> ليرة سورية قديمة"
                if lang == 'ar'
                else f"\nℹ️ Equivalent to <b>{_format_money(old_syp_amount)}</b> legacy Syrian pounds"
            )
            await self.notify_user(user_id, equivalent_line)

        # The QR belongs to the payment account (ShamCash), not to the customer's wallet.
        if qr_photo_id:
            caption = (
                f"💳 <b>بيانات الدفع — {name}</b>\n"
                f"العملة: <b>{currency}</b>\n"
                f"الحساب: <code>{account}</code>\n\n"
                f"📱 استخدم رمز QR أعلاه للدفع.\n"
                f"📦 الطلب: <b>#{order['order_number']}</b>"
            ) if lang == 'ar' else (
                f"💳 <b>Payment details — {name}</b>\n"
                f"Currency: <b>{currency}</b>\n"
                f"Account: <code>{account}</code>\n\n"
                f"📱 Use the QR code above to pay.\n"
                f"📦 Order: <b>#{order['order_number']}</b>"
            )
            try:
                await self._bot.send_photo(user_id, qr_photo_id, caption=caption, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Failed to send payment QR for order {order['order_number']}: {e}")

    async def notify_feedback(self, user: dict, message: str):
        """Notify admins of new feedback."""
        text = f"""
📨 <b>اقتراح جديد من عميل</b>

👤 من: @{user.get('username', 'بدون')}
🆔 ID: <code>{user['telegram_id']}</code>
📛 الاسم: {user.get('full_name', 'غير مسجل')}

💬 <b>الرسالة:</b>
{message}
"""
        await self.notify_admins(text)
