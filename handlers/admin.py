"""Admin handlers."""
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states import AdminStates

from keyboards.inline import admin_menu_keyboard, order_admin_keyboard, admin_verify_keyboard
from services.locale_service import locale_service
from services.notification_service import NotificationService
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
    """Show pending orders (new, not yet approved)."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        orders = await conn.fetch(
            "SELECT o.*, u.full_name, u.telegram_id AS user_tg FROM orders o "
            "JOIN users u ON o.user_id = u.id "
            "WHERE o.status = 'pending' ORDER BY o.created_at DESC"
        )

    if not orders:
        await callback.message.edit_text("✅ لا توجد طلبات معلقة للموافقة")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📦 <b>الطلبات المعلقة ({len(orders)})</b>",
        parse_mode='HTML'
    )

    for order in orders:
        text = (
            f"📦 <b>#{order['order_number']}</b>\n"
            f"👤 {html.escape(order['full_name'] or 'N/A')} (<code>{order['user_tg']}</code>)\n"
            f"💰 {order['amount_usdt']} USDT | 🌐 {order['network']}\n"
            f"💱 {order['payment_currency']} | 💵 {order['total_amount']:.2f}\n"
            f"📍 <code>{order['wallet_address'][:15]}...</code>\n"
            f"📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        await callback.message.answer(
            text,
            reply_markup=order_admin_keyboard(order['id'], order['status']),
            parse_mode='HTML'
        )

    await callback.answer()


@router.callback_query(F.data == "admin_active_orders")
async def admin_active_orders(callback: CallbackQuery):
    """Show ALL active orders that need admin action."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        orders = await conn.fetch(
            "SELECT o.*, u.full_name, u.telegram_id AS user_tg FROM orders o "
            "JOIN users u ON o.user_id = u.id "
            "WHERE o.status IN ('pending', 'waiting_payment', 'receipt_received', 'payment_confirmed') "
            "ORDER BY o.created_at DESC"
        )

    if not orders:
        await callback.message.edit_text("✅ لا توجد طلبات نشطة حالياً")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📋 <b>جميع الطلبات النشطة ({len(orders)})</b>\n"
        f"⏳ في انتظار الموافقة • 💳 في انتظار الدفع\n"
        f"📎 في انتظار مراجعة الإيصال • 🚀 في انتظار الإرسال",
        parse_mode='HTML'
    )

    for order in orders:
        status_icons = {
            'pending': '⏳',
            'waiting_payment': '💳',
            'receipt_received': '📎',
            'payment_confirmed': '🚀'
        }
        icon = status_icons.get(order['status'], '❓')
        status_names = {
            'pending': 'قيد الانتظار',
            'waiting_payment': 'بانتظار الدفع',
            'receipt_received': 'تم استلام الإيصال',
            'payment_confirmed': 'تم تأكيد الدفع'
        }

        text = (
            f"{icon} <b>#{order['order_number']}</b>\n"
            f"━━━ 👤 العميل ━━━\n"
            f"👤 الاسم: {html.escape(order['full_name'] or 'N/A')}\n"
            f"🆔 المعرف: <code>{order['user_tg']}</code>\n"
            f"━━━ 💳 الطلب ━━━\n"
            f"💰 المبلغ: {order['amount_usdt']} USDT\n"
            f"🌐 الشبكة: {order['network']}\n"
            f"📊 الحالة: {status_names.get(order['status'], order['status'])}\n"
            f"📅 التاريخ: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        await callback.message.answer(
            text,
            reply_markup=order_admin_keyboard(order['id'], order['status']),
            parse_mode='HTML'
        )
        # If order has a receipt and status is receipt_received, show the receipt image
        if order['status'] == 'receipt_received' and order.get('receipt_photo_id'):
            try:
                await callback.message.answer_photo(
                    order['receipt_photo_id'],
                    caption=f"📸 إيصال الدفع للطلب #{order['order_number']}"
                )
            except Exception as e:
                logger.error(f"Failed to send receipt photo for order {order['id']}: {e}")

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
            "SELECT o.*, u.full_name, u.username FROM orders o "
            "JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
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

        # Get user telegram_id
        user = await conn.fetchrow(
            "SELECT telegram_id FROM users WHERE id = $1", order['user_id']
        )

    # Notify user with receipt upload button
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    from services.notification_service import NotificationService
    from keyboards.inline import receipt_upload_keyboard

    notification = NotificationService(bot, Config.ADMIN_IDS)
    await notification.notify_order_approved(
        user['telegram_id'],
        dict(order)
    )

    # Send receipt upload button to user
    try:
        from services.locale_service import locale_service
        await bot.send_message(
            user['telegram_id'],
            "📎 بعد إتمام الدفع، اضغط على الزر أدناه لرفع الإيصال:",
            reply_markup=receipt_upload_keyboard(order['id'])
        )
    except Exception as e:
        logger.error(f"Failed to send receipt upload button: {e}")

    # Update admin notification: send NEW message with waiting_payment keyboard
    # so the admin can follow up when the customer pays
    admin_update_text = (
        f"💳 <b>تمت الموافقة على الطلب</b>\n\n"
        f"━━━ 👤 العميل ━━━\n"
        f"👤 الاسم: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 المعرف: <code>{user['telegram_id']}</code>\n"
        f"📱 المستخدم: @{order['username'] or 'N/A'}\n\n"
        f"━━━ 📦 تفاصيل الطلب ━━━\n"
        f"📦 #{order['order_number']}\n"
        f"💰 {order['amount_usdt']} USDT\n"
        f"🌐 {order['network']}\n"
        f"📍 <code>{order['wallet_address'][:15]}...</code>\n"
        f"⏱ المهلة: {Config.PAYMENT_TIMEOUT} دقيقة\n\n"
        f"بانتظار إرسال العميل للإيصال..."
    )
    import asyncio
    await asyncio.gather(*[
        bot.send_message(
            admin_id,
            admin_update_text,
            parse_mode='HTML'
        )
        for admin_id in Config.ADMIN_IDS
    ], return_exceptions=True)

    await callback.answer("✅ تمت الموافقة!")
    await callback.message.edit_text(f"✅ تمت الموافقة على طلب #{order['order_number']}")
    # Also send an admin menu link so they can go back
    from keyboards.inline import admin_menu_keyboard
    await callback.message.answer(
        "⚙️ <b>لوحة التحكم</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("admin_noop_"))
async def admin_noop(callback: CallbackQuery):
    """Placeholder for informational buttons."""
    await callback.answer("⏳ الطلب في انتظار الدفع من العميل...", show_alert=True)


@router.callback_query(F.data.startswith("admin_reject_"), ~F.data.startswith("admin_reject_receipt_"))
async def reject_order(callback: CallbackQuery):
    """Reject a pending order."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_reject_", ""))

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id AS user_tg, u.full_name FROM orders o "
            "JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True)
            return

        await conn.execute(
            "UPDATE orders SET status = 'rejected' WHERE id = $1",
            order_id
        )

    # Notify user their order was rejected
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    try:
        await bot.send_message(
            order['user_tg'],
            f"❌ <b>تم رفض طلبك</b>\n\n"
            f"📦 الطلب: #{order['order_number']}\n"
            f"💰 المبلغ: {order['amount_usdt']} USDT\n\n"
            f"يمكنك إنشاء طلب جديد من القائمة.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    await callback.answer("❌ تم رفض الطلب!")
    await callback.message.edit_text(
        f"❌ تم رفض الطلب #{order['order_number']}",
        parse_mode='HTML'
    )
    from keyboards.inline import admin_menu_keyboard
    await callback.message.answer(
        "⚙️ <b>لوحة التحكم</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode='HTML'
    )


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


@router.callback_query(F.data.startswith("verify_approve_"))
async def verify_approve_user(callback: CallbackQuery):
    """Approve user verification."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    telegram_id = int(callback.data.replace("verify_approve_", ""))

    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_verified = TRUE, verification_status = 'approved' WHERE telegram_id = $1",
            telegram_id
        )

    # Notify user
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)

    try:
        from keyboards.inline import main_menu_inline
        await bot.send_message(
            telegram_id,
            "🎉 <b>تم توثيق حسابك!</b>\n\nيمكنك الآن إنشاء طلبات الشحن.",
            parse_mode='HTML',
            reply_markup=main_menu_inline('ar')
        )
    except Exception as e:
        logger.error(f"Failed to notify user {telegram_id}: {e}")

    await callback.message.edit_text(
        f"✅ تم توثيق المستخدم <code>{telegram_id}</code> بنجاح!",
        parse_mode='HTML'
    )
    await callback.answer("✅ تم التوثيق!")


@router.callback_query(F.data.startswith("verify_reject_"))
async def verify_reject_user(callback: CallbackQuery):
    """Reject user verification."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    telegram_id = int(callback.data.replace("verify_reject_", ""))

    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT username, full_name FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if user:
            await conn.execute(
                "UPDATE users SET verification_status = 'rejected' WHERE telegram_id = $1",
                telegram_id
            )

    # Notify user — include specific reason if they lack a Telegram username
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)

    has_username = user and user.get('username')
    if not has_username:
        message_text = (
            "❌ <b>عذراً، لم يتم توثيق حسابك.</b>\n\n"
            "السبب: لا تملك اسم مستخدم (Username) في تيليغرام.\n\n"
            "📌 يرجى اتباع الخطوات التالية:\n"
            "1️⃣ افتح الإعدادات (Settings) في تيليغرام\n"
            "2️⃣ اضغط على اسمك\n"
            "3️⃣ اختر \"Set Username\" أو \"تعيين اسم مستخدم\"\n"
            "4️⃣ اختر اسماً (مثال: @your_name)\n"
            "5️⃣ احفظ التغييرات ثم أعد المحاولة بعد 5 دقائق"
        )
    else:
        message_text = (
            "❌ <b>عذراً، لم يتم توثيق حسابك.</b>\n\n"
            "يرجى التواصل مع الدعم للمساعدة."
        )

    try:
        await bot.send_message(telegram_id, message_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to notify user {telegram_id}: {e}")

    await callback.message.edit_text(
        f"❌ تم رفض توثيق المستخدم <code>{telegram_id}</code>.",
        parse_mode='HTML'
    )
    await callback.answer("❌ تم الرفض!")


@router.callback_query(F.data.startswith("admin_confirm_payment_"))
async def confirm_payment(callback: CallbackQuery):
    """Confirm payment received."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_confirm_payment_", ""))

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status = 'payment_confirmed' WHERE id = $1",
            order_id
        )
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name, u.username "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await callback.answer("الطلب غير موجود", show_alert=True)
        return

    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    from keyboards.inline import order_admin_keyboard
    import asyncio

    # Notify user
    try:
        await bot.send_message(
            order['telegram_id'],
            f"✅ <b>تم تأكيد الدفع!</b>\n\n📦 الطلب: #{order['order_number']}\n💰 المبلغ: {order['amount_usdt']} USDT\n🚀 جاري إرسال USDT إلى محفظتك...",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    # Notify admin with send-USDT button + customer info
    admin_text = (
        f"🚀 <b>تم تأكيد الدفع</b>\n\n"
        f"━━━ 👤 العميل ━━━\n"
        f"👤 الاسم: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 المعرف: <code>{order['telegram_id']}</code>\n"
        f"📱 المستخدم: @{order['username'] or 'N/A'}\n\n"
        f"━━━ 💳 تفاصيل الطلب ━━━\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT\n"
        f"🌐 الشبكة: {order['network']}\n"
        f"📍 عنوان المحفظة: <code>{order['wallet_address']}</code>\n\n"
        f"اضغط على 'إرسال USDT' بعد التنفيذ:"
    )

    # Send customer's wallet QR code if they uploaded one (NOT Sham Cash QR)
    wallet_qr_id = order.get('wallet_qr_photo_id')
    tasks = []
    for admin_id in Config.ADMIN_IDS:
        tasks.append(
            bot.send_message(
                admin_id,
                admin_text,
                reply_markup=order_admin_keyboard(order_id, 'payment_confirmed'),
                parse_mode='HTML'
            )
        )
        if wallet_qr_id:
            tasks.append(
                bot.send_photo(
                    admin_id,
                    wallet_qr_id,
                    caption=f"📸 <b>QR code لعنوان محفظة العميل</b> — {html.escape(order['full_name'] or 'N/A')}\n🌐 الشبكة: {order['network']}\nيمكن مسحه ضوئياً لإرسال USDT إلى عنوان العميل بدون خطأ",
                    parse_mode='HTML'
                )
            )
    await asyncio.gather(*tasks, return_exceptions=True)

    await callback.answer("✅ تم تأكيد الدفع!")
    await callback.message.edit_text(f"✅ تم تأكيد دفع الطلب #{order['order_number']}")
    # Send admin menu so they can continue
    from keyboards.inline import admin_menu_keyboard
    await callback.message.answer(
        "⚙️ <b>لوحة التحكم</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("admin_reject_receipt_"))
async def reject_receipt(callback: CallbackQuery):
    """Reject payment receipt."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_reject_receipt_", ""))

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status = 'waiting_payment' WHERE id = $1",
            order_id
        )
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await callback.answer("الطلب غير موجود", show_alert=True)
        return

    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    from keyboards.inline import receipt_upload_keyboard
    from datetime import datetime

    # Calculate remaining time before auto-cancel
    remaining = ""
    if order['payment_deadline']:
        delta = order['payment_deadline'] - datetime.now()
        remaining_seconds = int(delta.total_seconds())
        if remaining_seconds > 0:
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            if minutes > 0:
                remaining = f"⏱ الوقت المتبقي: <b>{minutes} دقيقة و{seconds} ثانية</b>"
            else:
                remaining = f"⏱ الوقت المتبقي: <b>{seconds} ثانية</b>"

    try:
        await bot.send_message(
            order['telegram_id'],
            f"⚠️ <b>الإيصال المرفوض</b>\n\n"
            f"عذراً {html.escape(order['full_name'] or 'عميلنا العزيز')}، الإيصال الذي أرسلته غير مطابق أو غير واضح.\n\n"
            f"📌 نرجو منك إرسال إيصال جديد وصحيح مع ضرورة ظهور:\n"
            f"• المبلغ المحوّل بوضوح\n"
            f"• اسم المستفيد (SHAMCASH)\n"
            f"• التاريخ\n\n"
            f"📎 اضغط على الزر أدناه لإعادة رفع الإيصال:\n"
            f"{remaining}\n\n"
            f"⚠️ تنبيه: في حال انتهت المهلة سيتم إلغاء الطلب تلقائياً.",
            reply_markup=receipt_upload_keyboard(order_id),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    await callback.answer("❌ تم رفض الإيصال!")
    await callback.message.edit_text(f"❌ تم رفض إيصال الطلب #{order['order_number']}")


@router.callback_query(F.data.startswith("admin_send_usdt_"))
async def send_usdt(callback: CallbackQuery, state: FSMContext):
    """Request TXID from admin to complete order."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_send_usdt_", ""))

    # Fetch order details to show wallet address
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name FROM orders o "
            "JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await callback.answer("الطلب غير موجود", show_alert=True)
        return

    await state.update_data(admin_txid_order_id=order_id, admin_txid='', admin_screenshot_id='')
    await callback.message.answer(
        f"🚀 <b>إرسال USDT</b>\n\n"
        f"━━━ 👤 العميل ━━━\n"
        f"👤 الاسم: {html.escape(order['full_name'] or 'N/A')}\n"
        f"🆔 المعرف: <code>{order['telegram_id']}</code>\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT\n"
        f"🌐 الشبكة: {order['network']}\n\n"
        f"━━━ 📍 عنوان الاستلام ━━━\n"
        f"<code>{order['wallet_address']}</code>\n\n"
        f"🔗 أرسل TXID (رقم المعاملة على السلسلة):\n"
        f"أو أرسل صورة التحويل مع TXID في التعليق",
        parse_mode='HTML'
    )

    await state.set_state(AdminStates.waiting_typing_txid)
    await callback.answer()


@router.message(AdminStates.waiting_typing_txid)
async def enter_txid(message: Message, state: FSMContext):
    """Handle TXID input — supports text TXID or photo with TXID in caption."""
    data = await state.get_data()
    order_id = data.get('admin_txid_order_id')

    if not order_id:
        await message.answer("❌ حدث خطأ. يرجى البدء من جديد.")
        await state.clear()
        return

    txid = ''
    screenshot_id = ''

    if message.photo:
        # Admin sent a photo — get TXID from caption
        screenshot_id = message.photo[-1].file_id
        txid = (message.caption or '').strip()
        if not txid:
            await message.answer(
                "❌ الصورة بدون TXID.\n"
                "أرسل الصورة مع كتابة TXID في التعليق،\n"
                "أو أرسل TXID كنص فقط:"
            )
            return
    else:
        txid = message.text.strip()

    if len(txid) < 5:
        await message.answer("❌ TXID غير صالح (يجب أن يكون 5 أحرف على الأقل). أرسل TXID صحيح:")
        return

    # Save data and ask for optional screenshot if not already provided
    await state.update_data(admin_txid=txid, admin_screenshot_id=screenshot_id)

    if not screenshot_id:
        await message.answer(
            "✅ تم استلام TXID!\n"
            "📸 يمكنك الآن إرسال صورة التحويل كدليل للعميل (اختياري):\n"
            "أو أرسل 'تخطي' لإكمال الطلب بدون صورة."
        )
        await state.set_state(AdminStates.waiting_transfer_screenshot)
    else:
        await complete_order(message, state, txid, screenshot_id, order_id)


@router.message(AdminStates.waiting_transfer_screenshot, F.photo)
async def enter_screenshot(message: Message, state: FSMContext):
    """Handle optional transfer screenshot from admin."""
    data = await state.get_data()
    order_id = data.get('admin_txid_order_id')
    txid = data.get('admin_txid', '')
    screenshot_id = message.photo[-1].file_id

    await complete_order(message, state, txid, screenshot_id, order_id)


@router.message(AdminStates.waiting_transfer_screenshot, F.text)
async def skip_screenshot(message: Message, state: FSMContext):
    """Skip transfer screenshot and complete order."""
    text = message.text.strip()
    if text in ['تخطي', 'skip', 'تخط']:
        data = await state.get_data()
        await complete_order(message, state, data.get('admin_txid', ''), '', data.get('admin_txid_order_id', 0))
    else:
        await message.answer("أرسل صورة التحويل أو اكتب 'تخطي' للإكمال بدون صورة.")


async def complete_order(msg: Message, state: FSMContext, txid: str, screenshot_id: str, order_id: int):
    """Finalize order: update DB, notify customer, send rating prompt."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status = 'completed', txid = $1, completed_at = NOW() WHERE id = $2",
            txid, order_id
        )
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name, u.username "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await msg.answer("❌ الطلب غير موجود.")
        await state.clear()
        return

    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    import asyncio

    # Build completion message for customer
    network_name = order['network'] or 'TRC20'
    completion_text = (
        f"✅ <b>تم إتمام طلبك بنجاح!</b>\n\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT إلى {network_name}\n"
        f"🔗 TXID: <code>{txid}</code>\n\n"
        f"🔄 يمكنك التحقق من المعاملة على المستكشف:"
    )

    # Generate explorer link
    if network_name == 'BEP20':
        explorer_url = f"https://bscscan.com/tx/{txid}"
    else:
        explorer_url = f"https://tronscan.org/#/transaction/{txid}"

    completion_text += f"\n<a href='{explorer_url}'>🔍 عرض على المستكشف</a>"

    try:
        if screenshot_id:
            await bot.send_photo(
                order['telegram_id'],
                screenshot_id,
                caption=completion_text,
                parse_mode='HTML'
            )
        else:
            await bot.send_message(
                order['telegram_id'],
                completion_text,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Failed to notify user {order['telegram_id']}: {e}")

    # Notify admin with customer info
    admin_done = (
        f"✅ <b>تم إكمال الطلب</b>\n\n"
        f"━━━ 👤 العميل ━━━\n"
        f"👤 الاسم: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 المعرف: <code>{order['telegram_id']}</code>\n"
        f"📱 المستخدم: @{order['username'] or 'N/A'}\n\n"
        f"━━━ 📦 تفاصيل الإتمام ━━━\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT\n"
        f"🌐 الشبكة: {network_name}\n"
        f"🔗 TXID: <code>{txid}</code>"
    )
    await asyncio.gather(*[
        bot.send_message(admin_id, admin_done, parse_mode='HTML')
        for admin_id in Config.ADMIN_IDS
    ], return_exceptions=True)

    await msg.answer(f"✅ تم إكمال الطلب #{order['order_number']} بنجاح!")

    # Send rating prompt
    try:
        from keyboards.inline import rating_keyboard
        await bot.send_message(
            order['telegram_id'],
            "⭐ يرجى تقييم تجربتك بالضغط على أحد النجوم:",
            reply_markup=rating_keyboard(order_id)
        )
    except Exception as e:
        logger.error(f"Failed to send rating prompt: {e}")

    await state.clear()


@router.callback_query(F.data.startswith("rate_"))
async def handle_rating(callback: CallbackQuery):
    """Handle customer rating."""
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer()
        return

    rating = int(parts[1])
    order_id = int(parts[2])

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET customer_rating = $1 WHERE id = $2",
            rating, order_id
        )

    await callback.message.edit_text(
        f"🙏 شكراً لتقييمك ({'⭐' * rating})!",
        parse_mode='HTML'
    )
    await callback.answer("✅ تم حفظ التقييم!")


# ───── Admin Update Rate ─────

@router.callback_query(F.data == "admin_update_rate")
async def admin_update_rate_start(callback: CallbackQuery, state: FSMContext):
    """Start exchange rate update flow."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        rate_row = await conn.fetchrow("SELECT rate, updated_at FROM exchange_rates ORDER BY id DESC LIMIT 1")

    current = f"{rate_row['rate']:,.0f}" if rate_row else "N/A"
    await callback.message.edit_text(
        f"💱 <b>سعر الصرف الحالي:</b> 1 USDT = {current} SYP\n\n"
        f"أرسل السعر الجديد (1 USDT = ? SYP):",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_rate)
    await callback.answer()


@router.message(AdminStates.waiting_rate)
async def admin_update_rate_save(message: Message, state: FSMContext):
    """Save new exchange rate."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return

    try:
        new_rate = float(message.text.strip().replace(',', ''))
        if new_rate <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ سعر غير صالح. أرسل رقماً صحيحاً (مثال: 15000):")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO exchange_rates (rate, updated_by) VALUES ($1, $2)",
            new_rate, message.from_user.id
        )

    await message.answer(f"✅ تم تحديث سعر الصرف: 1 USDT = {new_rate:,.0f} SYP")
    await state.clear()


# ───── Admin Settings Menu ─────

@router.callback_query(F.data == "admin_settings")
async def admin_settings_menu(callback: CallbackQuery):
    """Show admin settings menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    from keyboards.inline import settings_keyboard
    await callback.message.edit_text(
        "⚙️ <b>الإعدادات</b>\nاختر الإعداد الذي تريد تعديله:",
        reply_markup=settings_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_admin_settings")
async def cancel_admin_settings(callback: CallbackQuery, state: FSMContext):
    """Cancel admin settings input and return to settings menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    from keyboards.inline import settings_keyboard
    await callback.message.edit_text(
        "⚙️ <b>الإعدادات</b>\nاختر الإعداد الذي تريد تعديله:",
        reply_markup=settings_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "setting_rate")
async def setting_rate(callback: CallbackQuery, state: FSMContext):
    """Change rate from settings menu."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rate_row = await conn.fetchrow("SELECT rate FROM exchange_rates ORDER BY id DESC LIMIT 1")
    current = f"{rate_row['rate']:,.0f}" if rate_row else "N/A"
    await callback.message.edit_text(
        f"💱 <b>سعر الصرف الحالي:</b> 1 USDT = {current} SYP\n\n"
        f"أرسل السعر الجديد:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع للإعدادات", callback_data="cancel_admin_settings")]
        ])
    )
    await state.set_state(AdminStates.waiting_rate)
    await callback.answer()


@router.callback_query(F.data == "setting_fees")
async def setting_fees(callback: CallbackQuery, state: FSMContext):
    """Change fee settings."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"⚙️ <b>الرسوم الحالية</b>\n\n"
        f"📊 نسبة (%) : {Config.SERVICE_FEE_PERCENT}%\n"
        f"💵 ثابت : {Config.SERVICE_FEE_FIXED} {Config.SHAMCASH_SYP_ACCOUNT and 'SYP' or 'USD'}\n\n"
        f"أرسل النسبة المئوية للرسوم (مثال: 0.5):",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_fee_percent)
    await callback.answer()


# ───── Admin Note ─────

@router.callback_query(F.data.startswith("admin_note_"))
async def admin_note_start(callback: CallbackQuery, state: FSMContext):
    """Add admin note to order."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    order_id = int(callback.data.replace("admin_note_", ""))
    await state.update_data(admin_note_order_id=order_id, admin_note_mode=True)
    await callback.message.answer("📝 أرسل الملاحظة للإضافة للطلب:")
    await state.set_state(AdminStates.waiting_note_text)
    await callback.answer()


@router.message(AdminStates.waiting_note_text)
async def admin_save_note(message: Message, state: FSMContext):
    """Save admin note to order."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    data = await state.get_data()
    order_id = data.get('admin_note_order_id')
    note = message.text.strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET admin_notes = CONCAT(COALESCE(admin_notes, ''), $1, '\n') WHERE id = $2",
            f"[{message.from_user.id}] {note}", order_id
        )
    await message.answer(f"✅ تم إضافة الملاحظة للطلب #{order_id}")
    await state.clear()


@router.message(AdminStates.waiting_fee_percent)
async def admin_set_fee_percent(message: Message, state: FSMContext):
    """Set fee percent."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    try:
        pct = float(message.text.strip())
        if pct < 0 or pct > 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ نسبة غير صالحة (0-100). أرسل رقماً صحيحاً:")
        return
    # Save to Config is runtime only; store in DB or .env via admin note
    await message.answer(f"✅ تم تعيين نسبة الرسوم: {pct}%\n"
                         f"⚠️ ملاحظة: هذا التغيير مؤقت. غيّر SERVICE_FEE_PERCENT في المتغيرات البيئية للتبيت.")
    # We'll update Config at runtime (instance variable)
    Config.SERVICE_FEE_PERCENT = pct
    await state.clear()


@router.message(AdminStates.waiting_fee_fixed)
async def admin_set_fee_fixed(message: Message, state: FSMContext):
    """Set fixed fee."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    try:
        fixed = float(message.text.strip())
        if fixed < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ قيمة غير صالحة. أرسل رقماً صحيحاً:")
        return
    Config.SERVICE_FEE_FIXED = fixed
    await message.answer(f"✅ تم تعيين الرسوم الثابتة: {fixed}\n"
                         f"⚠️ هذا التغيير مؤقت.")
    await state.clear()


@router.callback_query(F.data == "setting_shamcash_usd")
async def setting_shamcash_usd(callback: CallbackQuery, state: FSMContext):
    """Set Sham Cash USD account."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"📱 <b>حساب شام كاش USD الحالي:</b>\n<code>{Config.SHAMCASH_USD_ACCOUNT}</code>\n\n"
        f"أرسل رقم حساب USD الجديد:",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_shamcash_usd)
    await callback.answer()


@router.message(AdminStates.waiting_shamcash_usd)
async def admin_set_shamcash_usd(message: Message, state: FSMContext):
    """Save new Sham Cash USD account."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    account = message.text.strip()
    Config.SHAMCASH_USD_ACCOUNT = account
    await message.answer(f"✅ تم تحديث حساب شام كاش USD:\n<code>{account}</code>", parse_mode='HTML')
    await state.clear()


@router.callback_query(F.data == "setting_shamcash_syp")
async def setting_shamcash_syp(callback: CallbackQuery, state: FSMContext):
    """Set Sham Cash SYP account."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"📱 <b>حساب شام كاش SYP الحالي:</b>\n<code>{Config.SHAMCASH_SYP_ACCOUNT}</code>\n\n"
        f"أرسل رقم حساب SYP الجديد:",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_shamcash_syp)
    await callback.answer()


@router.message(AdminStates.waiting_shamcash_syp)
async def admin_set_shamcash_syp(message: Message, state: FSMContext):
    """Save new Sham Cash SYP account."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    account = message.text.strip()
    Config.SHAMCASH_SYP_ACCOUNT = account
    await message.answer(f"✅ تم تحديث حساب شام كاش SYP:\n<code>{account}</code>", parse_mode='HTML')
    await state.clear()


@router.callback_query(F.data == "setting_shamcash_name")
async def setting_shamcash_name(callback: CallbackQuery, state: FSMContext):
    """Change Sham Cash account name."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"👤 <b>اسم حساب شام كاش الحالي:</b>\n{Config.SHAMCASH_NAME or 'N/A'}\n\n"
        f"أرسل الاسم الجديد لحساب شام كاش:",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_shamcash_name)
    await callback.answer()


@router.message(AdminStates.waiting_shamcash_name)
async def admin_set_shamcash_name(message: Message, state: FSMContext):
    """Save new Sham Cash name."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    name = message.text.strip()
    Config.SHAMCASH_NAME = name
    await message.answer(f"✅ تم تحديث اسم حساب شام كاش:\n{name}")
    await state.clear()


@router.callback_query(F.data == "setting_timeout")
async def setting_timeout(callback: CallbackQuery, state: FSMContext):
    """Change payment timeout."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"⏱ <b>مهلة الدفع الحالية:</b> {Config.PAYMENT_TIMEOUT} دقيقة\n\n"
        f"أرسل المهلة الجديدة بالدقائق:",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_timeout)
    await callback.answer()


@router.message(AdminStates.waiting_timeout)
async def admin_set_timeout(message: Message, state: FSMContext):
    """Save new payment timeout."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    try:
        timeout = int(message.text.strip())
        if timeout < 1 or timeout > 1440:
            raise ValueError
    except ValueError:
        await message.answer("❌ قيمة غير صالحة (1-1440 دقيقة). أرسل رقماً صحيحاً:")
        return
    Config.PAYMENT_TIMEOUT = timeout
    await message.answer(f"✅ تم تحديث مهلة الدفع: {timeout} دقيقة\n⚠️ هذا التغيير مؤقت.")
    await state.clear()


@router.callback_query(F.data == "setting_limits")
async def setting_limits(callback: CallbackQuery, state: FSMContext):
    """Change order limits."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"📊 <b>الحدود الحالية</b>\n\n"
        f"🔽 الحد الأدنى: {Config.MIN_ORDER} USDT\n"
        f"🔼 الحد الأقصى: {Config.MAX_ORDER} USDT\n\n"
        f"أرسل الحد الأدنى الجديد (USDT):",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_min_order)
    await callback.answer()


@router.message(AdminStates.waiting_min_order)
async def admin_set_min_order(message: Message, state: FSMContext):
    """Set min order limit."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    try:
        val = float(message.text.strip())
        if val < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ قيمة غير صالحة. أرسل رقماً صحيحاً (1+):")
        return
    Config.MIN_ORDER = val
    await message.answer(f"✅ تم تعيين الحد الأدنى: {val} USDT\nأرسل الحد الأقصى الجديد (USDT):")
    await state.set_state(AdminStates.waiting_max_order)
    await message.answer(f"أرسل الحد الأقصى الجديد (USDT):")


@router.message(AdminStates.waiting_max_order)
async def admin_set_max_order(message: Message, state: FSMContext):
    """Set max order limit."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    try:
        val = float(message.text.strip())
        if val < Config.MIN_ORDER:
            raise ValueError
    except ValueError:
        await message.answer(f"❌ قيمة غير صالحة. أرسل رقماً أكبر من الحد الأدنى ({Config.MIN_ORDER}):")
        return
    Config.MAX_ORDER = val
    await message.answer(f"✅ تم تعيين الحد الأقصى: {val} USDT\n⚠️ هذا التغيير مؤقت.")
    await state.clear()


@router.callback_query(F.data == "admin_menu")
async def admin_menu_back(callback: CallbackQuery):
    """Go back to admin panel."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    from keyboards.inline import admin_menu_keyboard
    await callback.message.edit_text(
        "⚙️ <b>لوحة التحكم</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()


# ───── Admin List Users (Alphabetical) ─────

@router.callback_query(F.data == "admin_list_users")
async def admin_list_users(callback: CallbackQuery):
    """List all verified/non-blocked users alphabetically."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT telegram_id, full_name, username, language, is_verified, is_blocked, created_at "
            "FROM users WHERE terms_accepted = TRUE AND is_blocked = FALSE "
            "ORDER BY full_name ASC NULLS LAST"
        )

    if not users:
        await callback.message.edit_text("📭 لا يوجد عملاء مسجلون.", parse_mode='HTML')
        await callback.answer()
        return

    # Build the user list in chunks to avoid message too long
    lines = []
    for i, u in enumerate(users, 1):
        name = u['full_name'] or '—'
        verified = "✅" if u['is_verified'] else "⏳"
        lang_flag = "🇸🇦" if u['language'] == 'ar' else "🇬🇧"
        lines.append(
            f"{i}. {verified} <b>{name}</b>\n"
            f"   🆔 <code>{u['telegram_id']}</code> | @{u['username'] or '—'} | {lang_flag}"
        )

    # Split into pages of 15 users each
    page_size = 15
    total_pages = (len(lines) + page_size - 1) // page_size
    page = 0  # 0-indexed

    def build_page(p):
        start = p * page_size
        end = start + page_size
        page_lines = lines[start:end]
        text = (
            f"📍 <b>قائمة العملاء</b> ({len(users)})\n"
            f"━━━━━━━━━━━━━━━━━━\n" +
            "\n".join(page_lines)
        )
        buttons = []
        if total_pages > 1:
            nav = []
            if p > 0:
                nav.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"users_page_{p-1}"))
            nav.append(InlineKeyboardButton(text=f"{p+1}/{total_pages}", callback_data="admin_noop"))
            if p < total_pages - 1:
                nav.append(InlineKeyboardButton(text="التالي ▶️", callback_data=f"users_page_{p+1}"))
            buttons.append(nav)
        buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_menu")])
        return text, InlineKeyboardMarkup(inline_keyboard=buttons)

    text, kb = build_page(page)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data.startswith("users_page_"))
async def admin_users_page(callback: CallbackQuery):
    """Navigate user list pages."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    page = int(callback.data.replace("users_page_", ""))

    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT telegram_id, full_name, username, language, is_verified, is_blocked, created_at "
            "FROM users WHERE terms_accepted = TRUE AND is_blocked = FALSE "
            "ORDER BY full_name ASC NULLS LAST"
        )

    lines = []
    for i, u in enumerate(users, 1):
        name = u['full_name'] or '—'
        verified = "✅" if u['is_verified'] else "⏳"
        lang_flag = "🇸🇦" if u['language'] == 'ar' else "🇬🇧"
        lines.append(
            f"{i}. {verified} <b>{name}</b>\n"
            f"   🆔 <code>{u['telegram_id']}</code> | @{u['username'] or '—'} | {lang_flag}"
        )

    page_size = 15
    total_pages = (len(lines) + page_size - 1) // page_size

    start = page * page_size
    end = start + page_size
    page_lines = lines[start:end]
    text = (
        f"📍 <b>قائمة العملاء</b> ({len(users)})\n"
        f"━━━━━━━━━━━━━━━━━━\n" +
        "\n".join(page_lines)
    )
    buttons = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"users_page_{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="admin_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="التالي ▶️", callback_data=f"users_page_{page+1}"))
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_menu")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode='HTML')
    await callback.answer()


# ───── Admin Backups ─────

@router.callback_query(F.data == "admin_backups")
async def admin_backups(callback: CallbackQuery):
    """Show backup info."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        order_count = await conn.fetchval("SELECT COUNT(*) FROM orders")
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        rate_count = await conn.fetchval("SELECT COUNT(*) FROM exchange_rates")
        feedback_count = await conn.fetchval("SELECT COUNT(*) FROM feedback_messages")
    await callback.message.edit_text(
        f"📋 <b>النسخ الاحتياطية</b>\n\n"
        f"📊 إحصائيات قاعدة البيانات:\n"
        f"👤 المستخدمون: {user_count}\n"
        f"📦 الطلبات: {order_count}\n"
        f"💱 أسعار الصرف: {rate_count}\n"
        f"✉️ الرسائل: {feedback_count}\n\n"
        f"🔹 يتم الاحتفاظ بالنسخ الاحتياطية لمدة {Config.BACKUP_RETENTION_DAYS} يوماً\n"
        f"🔹 تصدير يدوي غير متوفر حالياً - تواصل مع المطور.",
        parse_mode='HTML'
    )
    await callback.answer()


# ───── Admin Broadcast ─────

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Start broadcast message flow."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        "📨 <b>إرسال إشعار جماعي</b>\n\n"
        "⚠️ سيتم إرسال الرسالة إلى جميع المستخدمين المسجلين.\n"
        "أرسل نص الرسالة (يدعم HTML):",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()


@router.message(AdminStates.waiting_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    """Send broadcast to all users."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    text = message.text or message.caption or ""
    if not text.strip():
        await message.answer("❌ الرسالة فارغة. أرسل نص الرسالة:")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT telegram_id FROM users")
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    sent = 0
    failed = 0
    for u in users:
        try:
            await bot.send_message(u['telegram_id'], text, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
    await message.answer(
        f"📨 <b>نتيجة الإرسال الجماعي</b>\n\n"
        f"✅ تم الإرسال: {sent}\n"
        f"❌ فشل: {failed}\n"
        f"📊 المجموع: {len(users)}",
        parse_mode='HTML'
    )
    await state.clear()


# ───── Admin Maintenance Toggle ─────

async def _notify_users_maintenance(admin_msg: Message, locale_key: str = 'maintenance_notification'):
    """Broadcast maintenance notification to all active users."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT telegram_id, language FROM users WHERE terms_accepted = TRUE"
        )
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    sent = 0
    failed = 0
    for u in users:
        lang = u['language'] or 'ar'
        text = locale_service.get(locale_key, lang)
        try:
            await bot.send_message(u['telegram_id'], text, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
    await admin_msg.answer(
        f"📨 <b>إشعار الصيانة للمستخدمين</b>\n\n"
        f"✅ تم الإشعار: {sent}\n"
        f"❌ فشل: {failed}\n"
        f"📊 المجموع: {len(users)}",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_maintenance")
async def admin_maintenance(callback: CallbackQuery):
    """Toggle maintenance mode — checks for active orders first."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    currently_on = Config.get_maintenance_mode()

    if currently_on:
        # Turn off maintenance — no checks needed
        Config.set_maintenance_mode(False)
        await callback.message.edit_text(
            "✅ <b>تم إيقاف وضع الصيانة</b>\n\n"
            "البوت متاح للمستخدمين الآن.",
            parse_mode='HTML'
        )
        await callback.message.answer(
            "⚙️ <b>لوحة التحكم</b>",
            reply_markup=admin_menu_keyboard(),
            parse_mode='HTML'
        )
        await callback.answer()

        # Notify all users that maintenance ended
        await _notify_users_maintenance(callback.message, 'maintenance_ended')
        return

    # Turning ON — check for active orders first
    pool = await get_pool()
    async with pool.acquire() as conn:
        active_orders = await conn.fetch(
            "SELECT o.id, o.order_number, o.status, o.amount_usdt, "
            "u.full_name, u.telegram_id "
            "FROM orders o JOIN users u ON o.user_id = u.id "
            "WHERE o.status IN ('pending', 'waiting_payment', 'receipt_received', 'payment_confirmed')"
        )

    if active_orders:
        # Warn admin with details
        status_names = {
            'pending': '⏳ قيد الانتظار',
            'waiting_payment': '💳 انتظار الدفع',
            'receipt_received': '📎 قيد المراجعة',
            'payment_confirmed': '🚀 انتظار الإرسال',
        }
        lines = []
        for o in active_orders[:10]:  # Show first 10
            icon = status_names.get(o['status'], o['status'])
            lines.append(
                f"• #{o['order_number']} — {icon} — {o['full_name'] or 'N/A'} — {o['amount_usdt']} USDT"
            )
        detail_text = "\n".join(lines)
        remaining = len(active_orders) - 10
        if remaining > 0:
            detail_text += f"\n... و{remaining} طلب آخر"

        await callback.message.edit_text(
            f"⛔ <b>لا يمكن تفعيل وضع الصيانة</b>\n\n"
            f"يوجد <b>{len(active_orders)}</b> طلب نشط يجب إكمالها أولاً:\n\n"
            f"{detail_text}\n\n"
            f"⚠️ يرجى إنهاء جميع الطلبات النشطة ثم المحاولة مرة أخرى.",
            parse_mode='HTML'
        )
        await callback.message.answer(
            "⚙️ <b>لوحة التحكم</b>",
            reply_markup=admin_menu_keyboard(),
            parse_mode='HTML'
        )
        await callback.answer()
        return

    # No active orders — safe to enable maintenance
    Config.set_maintenance_mode(True)
    await callback.message.edit_text(
        f"🛑 <b>تم تفعيل وضع الصيانة</b>\n\n"
        f"جميع الطلبات مكتملة ✅\n"
        f"المستخدمون سيرون رسالة الصيانة.\n"
        f"المشرفون ما زالوا قادرين على الوصول.\n\n"
        f"لإيقاف الصيانة، اضغط على الزر مرة أخرى.",
        parse_mode='HTML'
    )
    await callback.message.answer(
        "⚙️ <b>لوحة التحكم</b>",
        reply_markup=admin_menu_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()

    # Notify all users
    await _notify_users_maintenance(callback.message)


@router.callback_query(F.data == "admin_maintenance_force")
async def admin_maintenance_force(callback: CallbackQuery):
    """Force enable maintenance even with active orders."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    Config.set_maintenance_mode(True)
    await callback.message.edit_text(
        "🛑 <b>تم تفعيل وضع الصيانة (قسري)</b>\n\n"
        "⚠️ تم تجاوز الطلبات النشطة.",
        parse_mode='HTML'
    )
    await callback.answer()

    # Notify all users
    await _notify_users_maintenance(callback.message)


# ───── Admin Search ─────

@router.callback_query(F.data == "admin_search_user")
async def admin_search_user(callback: CallbackQuery, state: FSMContext):
    """Search for a user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        "🔍 <b>بحث عن عميل</b>\n\n"
        "أرسل معرف المستخدم (ID) أو اسم المستخدم (@username):",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_search)
    await state.update_data(admin_search_type='user')
    await callback.answer()


@router.message(AdminStates.waiting_search)
async def admin_search_handler(message: Message, state: FSMContext):
    """Handle search queries for users or orders."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return
    data = await state.get_data()
    search_type = data.get('admin_search_type', 'user')
    query = message.text.strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        if search_type == 'user':
            # Try by telegram_id first
            if query.isdigit():
                rows = await conn.fetch("SELECT * FROM users WHERE telegram_id = $1", int(query))
            else:
                clean = query.replace('@', '')
                rows = await conn.fetch("SELECT * FROM users WHERE username ILIKE $1", f"%{clean}%")
            if not rows:
                await message.answer("❌ لم يتم العثور على مستخدم.")
            for u in rows:
                text = (
                    f"👤 <b>معلومات العميل</b>\n\n"
                    f"🆔 المعرف: <code>{u['telegram_id']}</code>\n"
                    f"📛 الاسم: {u['full_name'] or 'N/A'}\n"
                    f"📱 اليوزر: @{u['username'] or 'N/A'}\n"
                    f"🔰 التوثيق: {'✅' if u['is_verified'] else '❌'} ({u['verification_status']})\n"
                    f"🏦 شام كاش: {u['shamcash_account'] or 'N/A'}\n"
                    f"💬 اللغة: {u['language']}\n"
                    f"🚫 محظور: {'✅' if u['is_blocked'] else '❌'}\n"
                    f"📅 التسجيل: {u['created_at'].strftime('%Y-%m-%d')}"
                )
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                tid = u['telegram_id']
                actions = []
                if u['is_blocked']:
                    actions.append(InlineKeyboardButton(text="✅ فك الحظر", callback_data=f"admin_unban_{tid}"))
                else:
                    actions.append(InlineKeyboardButton(text="🚫 حظر", callback_data=f"admin_ban_{tid}"))
                actions.append(InlineKeyboardButton(text="🗑️ حذف", callback_data=f"admin_del_user_{tid}"))
                kb = InlineKeyboardMarkup(inline_keyboard=[actions])
                await message.answer(text, parse_mode='HTML', reply_markup=kb)
        elif search_type == 'order':
            row = await conn.fetchrow("SELECT o.*, u.full_name, u.telegram_id FROM orders o JOIN users u ON o.user_id = u.id WHERE o.order_number ILIKE $1", f"%{query}%")
            if not row:
                await message.answer("❌ لم يتم العثور على طلب.")
            else:
                text = (
                    f"📦 <b>الطلب #{row['order_number']}</b>\n\n"
                    f"👤 العميل: {row['full_name'] or 'N/A'} (<code>{row['telegram_id']}</code>)\n"
                    f"💰 {row['amount_usdt']} USDT → {row['network']}\n"
                    f"📍 المحفظة: <code>{row['wallet_address'][:20]}...</code>\n"
                    f"📊 الحالة: {row['status']}\n"
                    f"💱 السعر: 1 USDT = {row['exchange_rate']:,.0f} {row['payment_currency']}\n"
                    f"💵 الإجمالي: {row['total_amount']:.2f} {row['payment_currency']}\n"
                    f"📅 الإنشاء: {row['created_at'].strftime('%Y-%m-%d %H:%M')}"
                )
                await message.answer(text, parse_mode='HTML')
    await state.clear()


# ───── Admin Ban / Unban ─────

@router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban_user(callback: CallbackQuery):
    """Ban a user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    tid = int(callback.data.replace("admin_ban_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT full_name, telegram_id, is_blocked FROM users WHERE telegram_id = $1", tid
        )
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    if user['is_blocked']:
        await callback.answer("✅ المستخدم محظور بالفعل", show_alert=True)
        return

    name = user['full_name'] or 'N/A'
    await callback.message.edit_text(
        f"🚫 <b>تأكيد حظر المستخدم</b>\n\n"
        f"👤 {name}\n"
        f"🆔 <code>{tid}</code>\n\n"
        f"هل تريد حظر هذا المستخدم؟\n"
        f"لن يتمكن من إنشاء طلبات أو استخدام البوت.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأكيد الحظر", callback_data=f"admin_ban_confirm_{tid}"),
                InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_search_user")
            ]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban_confirm_"))
async def admin_ban_user_execute(callback: CallbackQuery):
    """Execute user ban."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    tid = int(callback.data.replace("admin_ban_confirm_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_blocked = TRUE WHERE telegram_id = $1", tid
        )
        await conn.execute(
            "INSERT INTO blocked_users (telegram_id, blocked_by) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            tid, callback.from_user.id
        )
    await callback.message.edit_text(
        f"✅ <b>تم حظر المستخدم</b>\n"
        f"🆔 <code>{tid}</code>",
        parse_mode='HTML'
    )
    await callback.message.answer(
        "⚙️ لوحة التحكم",
        reply_markup=admin_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban_user(callback: CallbackQuery):
    """Unban a user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    tid = int(callback.data.replace("admin_unban_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT full_name, telegram_id, is_blocked FROM users WHERE telegram_id = $1", tid
        )
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    if not user['is_blocked']:
        await callback.answer("✅ المستخدم غير محظور", show_alert=True)
        return

    name = user['full_name'] or 'N/A'
    await callback.message.edit_text(
        f"✅ <b>تأكيد فك الحظر</b>\n\n"
        f"👤 {name}\n"
        f"🆔 <code>{tid}</code>\n\n"
        f"هل تريد فك الحظر عن هذا المستخدم؟",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأكيد فك الحظر", callback_data=f"admin_unban_confirm_{tid}"),
                InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_search_user")
            ]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unban_confirm_"))
async def admin_unban_user_execute(callback: CallbackQuery):
    """Execute user unban."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    tid = int(callback.data.replace("admin_unban_confirm_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_blocked = FALSE WHERE telegram_id = $1", tid
        )
    await callback.message.edit_text(
        f"✅ <b>تم فك الحظر عن المستخدم</b>\n"
        f"🆔 <code>{tid}</code>",
        parse_mode='HTML'
    )
    await callback.message.answer(
        "⚙️ لوحة التحكم",
        reply_markup=admin_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_search_order")
async def admin_search_order_start(callback: CallbackQuery, state: FSMContext):
    """Search for an order."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        "🔍 <b>بحث عن طلب</b>\n\n"
        "أرسل رقم الطلب (مثال: ORD_20260730_...):",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_search)
    await state.update_data(admin_search_type='order')
    await callback.answer()


# ───── Admin Analytics ─────

@router.callback_query(F.data == "admin_analytics")
async def admin_analytics(callback: CallbackQuery):
    """Show analytics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_orders = await conn.fetchval("SELECT COUNT(*) FROM orders")
        completed_orders = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
        total_usdt = await conn.fetchval("SELECT COALESCE(SUM(amount_usdt), 0) FROM orders WHERE status = 'completed'")
        today_orders = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE created_at >= CURRENT_DATE")
        pending_count = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status IN ('pending', 'waiting_payment', 'receipt_received', 'payment_confirmed')")
        avg_rating = await conn.fetchval("SELECT COALESCE(ROUND(AVG(customer_rating), 1), 0) FROM orders WHERE customer_rating IS NOT NULL")
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        verified_count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_verified = TRUE")

    await callback.message.edit_text(
        f"📈 <b>التحليلات</b>\n\n"
        f"━━━ المستخدمون ━━━\n"
        f"👤 المجموع: {user_count}\n"
        f"✅ موثق: {verified_count}\n\n"
        f"━━━ الطلبات ━━━\n"
        f"📦 المجموع: {total_orders}\n"
        f"✅ مكتمل: {completed_orders}\n"
        f"⏳ معلق: {pending_count}\n"
        f"📅 اليوم: {today_orders}\n\n"
        f"━━━ الإيرادات ━━━\n"
        f"💰 إجمالي USDT المسلم: {total_usdt:.2f}\n\n"
        f"━━━ التقييمات ━━━\n"
        f"⭐ متوسط التقييم: {avg_rating}/5",
        parse_mode='HTML'
    )
    await callback.answer()


# ───── Admin Logs ─────

@router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    """Show recent logs."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    try:
        with open('logs/bot.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-30:]
            log_text = ''.join(lines)
        if len(log_text) > 3500:
            log_text = log_text[-3500:]
        await callback.message.edit_text(
            f"📝 <b>آخر السجلات</b>\n\n<pre>{log_text}</pre>",
            parse_mode='HTML'
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ فشل قراءة السجلات: {e}")


# ───── Admin Delete User ─────

@router.callback_query(F.data.startswith("admin_del_user_"))
async def admin_del_user(callback: CallbackQuery):
    """Confirm delete user and all their data."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    tid = int(callback.data.replace("admin_del_user_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT full_name, telegram_id FROM users WHERE telegram_id = $1", tid
        )
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return

    name = user['full_name'] or 'N/A'
    await callback.message.edit_text(
        f"🗑️ <b>تأكيد حذف المستخدم</b>\n\n"
        f"👤 {name}\n"
        f"🆔 <code>{tid}</code>\n\n"
        f"⚠️ <b>تحذير:</b> سيتم حذف جميع بيانات هذا المستخدم نهائياً:\n"
        f"• بيانات الحساب\n"
        f"• جميع الطلبات\n"
        f"• العناوين المحفوظة\n"
        f"• سجل الحظر والإقتراحات\n\n"
        f"🚫 <b>هذا الإجراء لا يمكن التراجع عنه.</b>\n\n"
        f"📨 سيتم إخطار المستخدم بحذف حسابه.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ تأكيد الحذف", callback_data=f"admin_del_confirm_{tid}"),
                InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_search_user")
            ]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del_confirm_"))
async def admin_del_user_execute(callback: CallbackQuery):
    """Execute user deletion and notify the user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    tid = int(callback.data.replace("admin_del_confirm_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, telegram_id, full_name, language FROM users WHERE telegram_id = $1", tid
        )
        if not user:
            await callback.answer("❌ المستخدم غير موجود", show_alert=True)
            return

        user_id = user['id']
        lang = user['language'] or 'ar'

        order_count = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE user_id = $1", user_id)
        addr_count = await conn.fetchval("SELECT COUNT(*) FROM saved_addresses WHERE user_id = $1", user_id)

        # Delete all user data
        await conn.execute("DELETE FROM orders WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM saved_addresses WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM blocked_users WHERE telegram_id = $1", tid)
        await conn.execute("DELETE FROM feedback_messages WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM audit_logs WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)

        # Log the action
        await conn.execute(
            "INSERT INTO audit_logs (user_id, admin_id, action, details, severity) VALUES ($1, $2, $3, $4, $5)",
            None, callback.from_user.id, 'user_deleted',
            f"Deleted user {user['full_name'] or 'N/A'} (tg:{tid}). Orders: {order_count}, Addresses: {addr_count}",
            'warning'
        )

    # Notify the user
    try:
        from aiogram import Bot
        from config import Config
        bot = Bot(token=Config.BOT_TOKEN)
        if lang == 'ar':
            await bot.send_message(
                tid,
                "🗑️ <b>تم حذف حسابك</b>\n\n"
                "تم حذف حسابك وجميع بياناتك من نظامنا.\n\n"
                "إذا كان لديك أي استفسار، يمكنك التواصل مع الدعم.",
                parse_mode='HTML'
            )
        else:
            await bot.send_message(
                tid,
                "🗑️ <b>Your Account Has Been Deleted</b>\n\n"
                "Your account and all associated data have been deleted from our system.\n\n"
                "If you have any questions, please contact support.",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Failed to notify deleted user {tid}: {e}")

    await callback.message.edit_text(
        f"✅ <b>تم حذف المستخدم</b>\n"
        f"🆔 <code>{tid}</code>\n"
        f"📊 تم حذف {order_count} طلب/طلبات\n"
        f"📍 تم حذف {addr_count} عنوان/عناوين محفوظة\n\n"
        f"📨 تم إخطار المستخدم.",
        parse_mode='HTML'
    )
    await callback.message.answer(
        "⚙️ لوحة التحكم",
        reply_markup=admin_menu_keyboard()
    )
    await callback.answer()


# ───── Admin Note (already handled above with waiting_note_text) ─────
