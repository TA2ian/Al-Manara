"""Admin handlers."""
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
        await conn.execute(
            "UPDATE users SET verification_status = 'rejected' WHERE telegram_id = $1",
            telegram_id
        )

    # Notify user
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)

    try:
        await bot.send_message(
            telegram_id,
            "❌ <b>عذراً، لم يتم توثيق حسابك.</b>\n\nيرجى التواصل مع الدعم للمساعدة.",
            parse_mode='HTML'
        )
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
            "SELECT o.*, u.telegram_id FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await callback.answer("الطلب غير موجود", show_alert=True)
        return

    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    from keyboards.inline import order_admin_keyboard

    # Notify user
    try:
        await bot.send_message(
            order['telegram_id'],
            f"✅ <b>تم تأكيد الدفع!</b>\n\n📦 الطلب: #{order['order_number']}\n💰 المبلغ: {order['amount_usdt']} USDT\n🚀 جاري إرسال USDT إلى محفظتك...",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    # Notify admin with send-USDT button
    admin_text = (
        f"🚀 <b>تم تأكيد الدفع</b>\n\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT\n"
        f"🌐 الشبكة: {order['network']}\n"
        f"📍 عنوان المحفظة: <code>{order['wallet_address']}</code>\n\n"
        f"اضغط على 'إرسال USDT' بعد التنفيذ:"
    )
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=order_admin_keyboard(order_id, 'payment_confirmed'),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    await callback.answer("✅ تم تأكيد الدفع!")
    await callback.message.edit_text(f"✅ تم تأكيد دفع الطلب #{order['order_number']}")


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
            "SELECT o.*, u.telegram_id FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await callback.answer("الطلب غير موجود", show_alert=True)
        return

    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    from keyboards.inline import receipt_upload_keyboard

    try:
        await bot.send_message(
            order['telegram_id'],
            "❌ <b>الإيصال غير صحيح</b>\n\nيرجى إرسال إيصال صحيح (صورة واضحة للتحويل):",
            reply_markup=receipt_upload_keyboard(order_id)
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

    await state.update_data(admin_txid_order_id=order_id, admin_txid='', admin_screenshot_id='')
    await callback.message.answer(
        "🔗 أرسل TXID (رقم المعاملة على السلسلة):\n"
        "أو أرسل صورة التحويل وسأخذ TXID من التعليق"
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
            "SELECT o.*, u.telegram_id FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await msg.answer("❌ الطلب غير موجود.")
        await state.clear()
        return

    bot = Bot(token=Config.BOT_TOKEN)

    # Build completion message for customer
    completion_text = (
        f"✅ <b>تم إتمام طلبك بنجاح!</b>\n\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT إلى {order['network']}\n"
        f"🔗 TXID: <code>{txid}</code>\n\n"
        f"🔄 يمكنك التحقق من المعاملة على المستكشف:"
    )

    # Generate explorer link
    if order['network'] == 'BEP20':
        explorer_url = f"https://bscscan.com/tx/{txid}"
    else:
        explorer_url = f"https://tronscan.org/#/transaction/{txid}"

    completion_text += f"\n<a href='{explorer_url}'>🔍 عرض على المستكشف</a>"

    try:
        if screenshot_id:
            # Send photo first with caption
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

    await msg.answer(f"✅ تم إكمال الطلب #{order['order_number']} وإرسال التأكيد للعميل مع TXID!")

    # Send rating prompt
    try:
        await bot.send_message(
            order['telegram_id'],
            "⭐ يرجى تقييم تجربتك بالضغط على أحد النجوم:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⭐", callback_data=f"rate_1_{order_id}"),
                    InlineKeyboardButton(text="⭐⭐", callback_data=f"rate_2_{order_id}"),
                    InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"rate_3_{order_id}"),
                    InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"rate_4_{order_id}"),
                    InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"rate_5_{order_id}")
                ]
            ])
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
