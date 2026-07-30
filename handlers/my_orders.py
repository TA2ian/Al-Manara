"""My orders handlers."""
import html
import io
import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from states import ReceiptStates
from keyboards.inline import main_menu_inline, receipt_upload_keyboard, order_admin_keyboard, orders_pagination_keyboard
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from services.receipt_verifier import ReceiptVerifier
from database import get_pool
from config import Config

logger = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 5


async def _format_orders_page(pool, user_id: int, lang: str, page: int = 1):
    """Build orders text and pagination info for a given page. Returns (text, total_pages, orders_list) or (None, 0, []) if no orders."""
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE user_id = $1", user_id
        )
        if total == 0:
            return None, 0, []

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * PAGE_SIZE

        orders = await conn.fetch(
            "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            user_id, PAGE_SIZE, offset
        )

    lines = [f"📋 <b>{locale_service.get('my_orders', lang)}</b> — ({page}/{total_pages})"]
    for order in orders:
        status_key = f"order_status_{order['status']}"
        status_text = locale_service.get(status_key, lang)
        lines.append(
            f"\n━━━━━━━━━━━━━━━\n"
            f"📦 <b>#{order['order_number']}</b>\n"
            f"💰 {order['amount_usdt']} USDT ({order['network']})\n"
            f"📊 {status_text}\n"
            f"📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )

    text = "\n".join(lines)
    return text, total_pages, orders


@router.message(F.text.in_(["📋 طلباتي", "📋 Orders"]))
async def show_my_orders(message: Message):
    """Show user's orders with pagination."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

    if not user:
        await message.answer("Please start the bot first: /start")
        return

    lang = user['language']
    text, total_pages, orders = await _format_orders_page(pool, user['id'], lang, 1)

    if not orders:
        await message.answer(locale_service.get('no_orders', lang))
        return

    await message.answer(
        text,
        parse_mode='HTML',
        reply_markup=orders_pagination_keyboard(1, total_pages, lang)
    )

    # For orders on page 1 that have action buttons, send them individually below
    for order in orders:
        if order['status'] == 'waiting_payment':
            await message.answer(
                f"📎 <b>#{order['order_number']}</b> — رفع الإيصال:",
                parse_mode='HTML',
                reply_markup=receipt_upload_keyboard(order['id'], lang)
            )


@router.callback_query(F.data.startswith("orders_page_"))
async def handle_orders_page(callback: CallbackQuery):
    """Handle pagination navigation for orders list."""
    page = int(callback.data.replace("orders_page_", ""))
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1",
            callback.from_user.id
        )

    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return

    lang = user['language']
    text, total_pages, orders = await _format_orders_page(pool, user['id'], lang, page)

    if not orders:
        await callback.answer("📭 لا توجد طلبات", show_alert=True)
        return

    await callback.message.edit_text(
        text,
        parse_mode='HTML',
        reply_markup=orders_pagination_keyboard(page, total_pages, lang)
    )
    await callback.answer()


@router.callback_query(F.data == "close_orders_list")
async def close_orders_list(callback: CallbackQuery):
    """Dismiss the orders list."""
    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_text("❌ تم الإغلاق.")
    await callback.answer()


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
    """Handle receipt photo upload with AI verification."""
    data = await state.get_data()
    order_id = data.get('receipt_order_id')

    if not order_id:
        await message.answer("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
        await state.clear()
        return

    photo = message.photo[-1]
    photo_id = photo.file_id

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name, u.shamcash_account "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id
        )

    if not order:
        await message.answer("❌ الطلب غير موجود.")
        await state.clear()
        return

    # Download the image for OCR analysis
    bot = Bot(token=Config.BOT_TOKEN)
    try:
        file_info = await bot.get_file(photo_id)
        image_file = await bot.download_file(file_info.file_path)
        image_bytes = image_file.read()
    except Exception as e:
        logger.error(f"Failed to download receipt image: {e}")
        image_bytes = None

    verification_result = None
    if image_bytes:
        # Run OCR verification
        expected_total = float(order['total_amount'])
        verification_result = await ReceiptVerifier.analyze_receipt(
            image_bytes, expected_total
        )
        logger.info(f"Receipt verification result: {verification_result}")

    # Determine status and message based on verification
    auto_verified = False
    verification_note = ""

    if verification_result:
        if verification_result['confidence'] == 'high':
            auto_verified = True
            verification_note = f"\n✅ <b>تحقق آلي:</b> {verification_result['message']}"
        elif verification_result['confidence'] == 'medium':
            verification_note = f"\n⚠️ <b>تحقق آلي:</b> {verification_result['message']}"
        elif verification_result['confidence'] == 'low':
            verification_note = f"\n⚠️ <b>تحقق آلي:</b> {verification_result['message']}"
        elif verification_result['confidence'] == 'none':
            verification_note = (
                "\n❌ <b>تحقق آلي:</b> لم يتم التعرف على أي نص في الصورة. "
                "قد لا تكون صورة إيصال صالحة."
            )
        else:
            verification_note = "\n⚠️ <b>تحقق آلي:</b> فشل تحليل الصورة - يرجى المراجعة اليدوية"

    new_status = 'receipt_received'
    await pool.execute(
        "UPDATE orders SET receipt_photo_id = $1, receipt_upload_count = receipt_upload_count + 1, status = $2 WHERE id = $3",
        photo_id, new_status, order_id
    )

    user_msg = "✅ تم استلام إيصالك! جاري مراجعة الإدارة..."
    if auto_verified:
        user_msg += "\n✅ تم التحقق من الإيصال آلياً."
    elif verification_result and verification_result['confidence'] == 'none':
        user_msg += "\n⚠️ لم يتم التعرف على الإيصال. سيتم مراجعته من قبل الإدارة."

    await message.answer(user_msg)

    # Notify admins with verification info + full customer details + order review
    created_at_str = order['created_at'].strftime('%Y-%m-%d %H:%M')
    admin_text = (
        f"📎 <b>إيصال دفع - مراجعة كاملة</b>\n\n"
        f"━━━ 💳 معلومات الدفع ━━━\n"
        f"📦 الطلب: <b>#{order['order_number']}</b>\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT -> {order['network']}\n"
        f"💱 سعر الصرف: 1 USDT = {order['exchange_rate']:,.0f} {order['payment_currency']}\n"
        f"💵 الإجمالي المطلوب: {order['total_amount']:.2f} {order['payment_currency']}\n\n"
        f"━━━ 👤 معلومات العميل ━━━\n"
        f"👤 الاسم: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 المعرف: <code>{order['user_telegram_id']}</code>\n"
        f"📱 المستخدم: @{message.chat.username or 'N/A'}\n"
        f"🏦 شام كاش: <code>{html.escape(order['shamcash_account'] or 'N/A')}</code>\n\n"
        f"━━━ 📍 عنوان الـUSDT ━━━\n"
        f"🌐 الشبكة: {order['network']}\n"
        f"📍 المحفظة: <code>{order['wallet_address']}</code>\n\n"
        f"━━━ 🤖 التحقق الآلي ━━━"
        f"{verification_note}" + (
            ""
            if not verification_result or not verification_result.get('extracted_amounts')
            else f"\n📊 المبالغ المستخرجة: {', '.join(f'{a:.2f}' for a in verification_result['extracted_amounts'][:5])}"
        )
        + f"\n\n━━━ 📋 ملخص الطلب ━━━\n"
        f"📅 تاريخ الإنشاء: {created_at_str}\n"
        f"📊 الحالة: قيد المراجعة\n"
        f"💰 USDT: {order['amount_usdt']}\n"
        f"💱 الأساسي: {order['base_amount']:.2f} {order['payment_currency']}\n"
        f"📈 رسوم ({order['fee_percent']}%): {order['fee_amount']:.2f} {order['payment_currency']}"
    )

    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=order_admin_keyboard(order_id, new_status),
                parse_mode='HTML'
            )
            if photo_id:
                await bot.send_photo(admin_id, photo_id, caption=f"📸 إيصال الدفع للطلب #{order['order_number']}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    await state.clear()
