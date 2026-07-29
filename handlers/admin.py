"""Admin handlers."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from keyboards.inline import admin_menu_keyboard, order_admin_keyboard
from services.locale_service import locale_service
from database import get_pool
from config import Config

router = Router()


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in Config.ADMIN_IDS


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Show admin panel."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        return

    await message.answer(
        "⚙️ <b>لوحة التحكم</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_pending_orders")
async def pending_orders(callback: CallbackQuery):
    """Show pending orders."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        orders = await conn.fetch(
            "SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC"
        )

    if not orders:
        await callback.message.edit_text("لا توجد طلبات معلقة")
        return

    for order in orders:
        text = f"""
📦 طلب #{order['order_number']}

👤 المستخدم: {order['user_id']}
💰 المبلغ: {order['amount_usdt']} USDT
🌐 الشبكة: {order['network']}
💱 العملة: {order['payment_currency']}
📅 التاريخ: {order['created_at'].strftime('%Y-%m-%d %H:%M')}
"""
        await callback.message.answer(
            text,
            reply_markup=order_admin_keyboard(order['id'], order['status']),
            parse_mode='HTML'
        )

    await callback.answer()


@router.callback_query(F.data.startswith("admin_approve_"))
async def approve_order(callback: CallbackQuery):
    """Approve order."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_approve_", ""))

    pool = await get_pool()

    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT * FROM orders WHERE id = $1", order_id
        )

        if not order:
            await callback.answer("Order not found", show_alert=True)
            return

        # Update order status
        from datetime import datetime, timedelta
        deadline = datetime.now() + timedelta(minutes=Config.PAYMENT_TIMEOUT)

        await conn.execute(
            "UPDATE orders SET status = 'waiting_payment', approved_at = NOW(), payment_deadline = $1 WHERE id = $2",
            deadline, order_id
        )

        # Get user
        user = await conn.fetchrow(
            "SELECT telegram_id FROM users WHERE id = $1", order['user_id']
        )

    # Notify user
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    from services.notification_service import NotificationService

    notification = NotificationService(bot, Config.ADMIN_IDS)
    await notification.notify_order_approved(
        user['telegram_id'],
        dict(order)
    )

    await callback.answer("✅ تمت الموافقة!")
    await callback.message.edit_text(f"✅ تمت الموافقة على طلب #{order['order_number']}")


@router.callback_query(F.data == "admin_dashboard")
async def admin_dashboard(callback: CallbackQuery):
    """Show admin dashboard."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        today_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE created_at >= CURRENT_DATE"
        )
        today_completed = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE status = 'completed' AND completed_at >= CURRENT_DATE"
        )
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE status = 'pending'"
        )
        total_amount = await conn.fetchval(
            "SELECT COALESCE(SUM(amount_usdt), 0) FROM orders WHERE created_at >= CURRENT_DATE"
        )

    text = f"""
📊 <b>لوحة التحكم - اليوم</b>

┌─────────┐ ┌─────────┐ ┌─────────┐
│  📦 {today_orders}   │ │  ✅ {today_completed}   │ │  ⏳ {pending}   │
│ طلبات   │ │ مكتمل   │ │ معلق    │
└─────────┘ └─────────┘ └─────────┘

💰 إجمالي: {total_amount} USDT

[📦 الطلبات] [📈 التحليلات] [⚙️ الإعدادات]
"""

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=admin_menu_keyboard())
    await callback.answer()
