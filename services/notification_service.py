"""Notification service."""
import logging
from aiogram import Bot

logger = logging.getLogger(__name__)


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
💰 المبلغ: {order['amount_usdt']} USDT
🌐 الشبكة: {order['network']}
💱 العملة: {order['payment_currency']}

[📋 عرض التفاصيل]
"""
        await self.notify_admins(text)

    async def notify_order_approved(self, user_id: int, order: dict):
        """Notify user that order is approved."""
        from services.locale_service import locale_service
        from config import Config

        text = locale_service.get(
            'order_approved',
            'ar',
            order_number=order['order_number'],
            timeout=Config.PAYMENT_TIMEOUT,
            account=Config.SHAMCASH_SYP_ACCOUNT if order['payment_currency'] == 'SYP' else Config.SHAMCASH_USD_ACCOUNT,
            name=Config.SHAMCASH_NAME,
            amount=order['total_amount'],
            currency=order['payment_currency']
        )

        await self.notify_user(user_id, text)

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
