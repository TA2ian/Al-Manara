"""My orders handlers."""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import ReceiptStates
from keyboards.inline import main_menu_inline, receipt_upload_keyboard
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from database import get_pool
from config import Config

router = Router()


@router.message(F.text.in_(["📋 طلباتي", "📋 Orders"]))
async def show_my_orders(message: Message):
    """Show user's orders with action buttons."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

        if not user:
            await message.answer("Please start the bot first: /start")
            return

        orders = await conn.fetch(
            "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10",
            user['id']
        )

    lang = user['language']

    if not orders:
        await message.answer(locale_service.get('no_orders', lang))
        return

    await message.answer(
        f"📋 <b>{locale_service.get('my_orders', lang)}</b>",
        parse_mode='HTML'
    )

    for order in orders:
        status_key = f"order_status_{order['status']}"
        status_text = locale_service.get(status_key, lang)

        text = (
            f"📦 <b>#{order['order_number']}</b>\n"
            f"💰 {order['amount_usdt']} USDT ({order['network']})\n"
            f"📊 {status_text}\n"
            f"📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )

        # Show action button for orders waiting payment
        if order['status'] == 'waiting_payment':
            await message.answer(
                text,
                parse_mode='HTML',
                reply_markup=receipt_upload_keyboard(order['id'], lang)
            )
        else:
            await message.answer(text, parse_mode='HTML')

    await message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )


@router.callback_query(F.data.startswith("upload_receipt_"))
async def start_receipt_upload(callback: CallbackQuery, state: FSMContext):
    """Start receipt upload from My Orders."""
    order_id = int(callback.data.replace("upload_receipt_", ""))

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT * FROM orders WHERE id = $1", order_id
        )

    if not order:
        await callback.answer("الطلب غير موجود", show_alert=True)
        return

    if order['status'] != 'waiting_payment':
        await callback.answer("لا يمكن رفع إيصال لهذا الطلب حالياً", show_alert=True)
        return

    await state.update_data(receipt_order_id=order_id)
    await callback.message.answer(
        f"📎 أرسل صورة الإيصال للطلب #{order['order_number']}\n"
        "(مثل صورة التحويل من شام كاش):"
    )
    await state.set_state(ReceiptStates.waiting_receipt)
    await callback.answer()


@router.message(ReceiptStates.waiting_receipt, F.photo)
async def handle_receipt_upload(message: Message, state: FSMContext):
    """Handle receipt photo upload."""
    data = await state.get_data()
    order_id = data.get('receipt_order_id')

    if not order_id:
        await message.answer("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
        await state.clear()
        return

    photo_id = message.photo[-1].file_id

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET receipt_photo_id = $1, receipt_upload_count = receipt_upload_count + 1, status = 'receipt_received' WHERE id = $2",
            photo_id, order_id
        )

        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id AS user_telegram_id FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await message.answer("❌ الطلب غير موجود.")
        await state.clear()
        return

    await message.answer("✅ تم استلام إيصالك! جاري مراجعة الإدارة...")

    # Notify admins
    bot = Bot(token=Config.BOT_TOKEN)
    from keyboards.inline import order_admin_keyboard

    admin_text = (
        f"📎 <b>تم رفع إيصال دفع</b>\n\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"👤 المستخدم: @{message.chat.username or 'N/A'}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT\n"
    )
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=order_admin_keyboard(order_id, 'receipt_received'),
                parse_mode='HTML'
            )
            await bot.send_photo(admin_id, photo_id, caption=f"📸 إيصال الطلب #{order['order_number']}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to notify admin {admin_id}: {e}")

    await state.clear()
