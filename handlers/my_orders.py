"""My orders handlers."""
import html
import io
import logging
from decimal import Decimal, InvalidOperation

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
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

MAX_RECEIPT_ATTEMPTS = 3


def _format_amount(value) -> str:
    """Format monetary values for Telegram display with exactly two decimals."""
    try:
        return f"{Decimal(str(value)):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


def _format_usdt(value) -> str:
    """Format USDT consistently across the receipt/admin view."""
    return _format_amount(value)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _verification_fail_keyboard(order_id: int, lang: str) -> InlineKeyboardMarkup:
    """Keyboard shown when auto-verification fails — retry or send to admin."""
    retry_text = "📎 إعادة رفع الإيصال" if lang == 'ar' else "📎 Re-upload Receipt"
    manual_text = "👨‍💼 أرسل للمشرف للمراجعة مباشرة" if lang == 'ar' else "👨‍💼 Send to Admin for Review"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=retry_text, callback_data=f"retry_receipt_{order_id}")],
        [InlineKeyboardButton(text=manual_text, callback_data=f"manual_review_{order_id}")],
    ])


async def _notify_admins_receipt(
    bot: Bot,
    order: dict,
    photo_id: str,
    verification_result: dict,
    username: str,
    is_auto_verified: bool,
):
    """Send receipt notification with full details to all admins."""
    order_id = order['id']
    new_status = 'receipt_received'

    created_at_str = order['created_at'].strftime('%Y-%m-%d %H:%M')

    # Build verification block
    if verification_result and verification_result.get('success'):
        v = verification_result
        score = v.get('score', 0)
        score_label = v.get('score_label', 'منخفضة')
        shamcash_fields = v.get('fields', {})
        shamcash_matches = v.get('matches', {})

        ver_block = "\n━━━ 🤖 التحقق الآلي من شام كاش ━━━\n"

        if is_auto_verified:
            ver_block += f"✅ <b>التحقق ناجح — نسبة الثقة {score}% ({score_label})</b>\n"
        else:
            ver_block += f"⚠️ <b>التحقق آلي — نسبة الثقة {score}% ({score_label})</b>\n"

        # Add per-field results
        for detail in v.get('details', []):
            ver_block += f"{detail}\n"

        # Show extracted raw data
        ver_block += "\n📄 <b>البيانات المستخرجة:</b>\n"
        if shamcash_fields.get('date'):
            ver_block += f"📅 التاريخ: {shamcash_fields['date']}\n"
        if shamcash_fields.get('sender_name'):
            ver_block += f"👤 اسم المرسل: {shamcash_fields['sender_name']}\n"
        if shamcash_fields.get('recipient_name'):
            ver_block += f"👤 اسم المستلم: {shamcash_fields['recipient_name']}\n"
        if shamcash_fields.get('amount', 0) > 0:
            ver_block += f"💰 المبلغ المستخرج: {_format_amount(shamcash_fields['amount'])}\n"

    else:
        ver_block = "\n━━━ 🤖 التحقق الآلي ━━━\n"
        ver_block += "⚠️ تعذر إجراء التحقق الآلي — يرجى المراجعة اليدوية\n"

    amount_usdt = _format_usdt(order['amount_usdt'])
    exchange_rate = f"{Decimal(str(order['exchange_rate'])):,.0f}"
    total_amount = _format_amount(order['total_amount'])
    base_amount = _format_amount(order['base_amount'])
    fee_percent = _format_amount(order['fee_percent'])
    fee_amount = _format_amount(order['fee_amount'])
    payment_currency = html.escape(order['payment_currency'])

    admin_text = (
        f"📎 <b>إيصال دفع — مراجعة كاملة</b>\n\n"
        f"━━━ 💳 معلومات الدفع ━━━\n"
        f"📦 الطلب: <b>#{order['order_number']}</b>\n"
        f"💰 المبلغ: <b>{amount_usdt} USDT</b> → {order['network']}\n"
        f"💱 سعر الصرف: 1 USDT = {exchange_rate} {payment_currency}\n"
        f"💵 الإجمالي المطلوب: <b>{total_amount} {payment_currency}</b>\n\n"
        f"━━━ 👤 معلومات العميل ━━━\n"
        f"👤 الاسم: <b>{html.escape(order.get('full_name', order.get('customer_name', '') or 'N/A'))}</b>\n"
        f"🆔 المعرف: <code>{order.get('user_telegram_id', '')}</code>\n"
        f"📱 المستخدم: @{username or 'N/A'}\n"
        f"🏦 شام كاش: <code>{html.escape(order.get('shamcash_account', order.get('customer_shamcash', '') or 'N/A'))}</code>\n\n"
        f"━━━ 📍 عنوان الـUSDT ━━━\n"
        f"🌐 الشبكة: {order['network']}\n"
        f"📍 المحفظة: <code>{order['wallet_address']}</code>\n\n"
        f"{ver_block}"
        f"\n━━━ 📋 ملخص الطلب ━━━\n"
        f"📅 تاريخ الإنشاء: {created_at_str}\n"
        f"📊 الحالة: قيد المراجعة{' (تحقق آلي ناجح)' if is_auto_verified else ''}\n"
        f"💰 USDT: {amount_usdt}\n"
        f"💱 الأساسي: {base_amount} {payment_currency}\n"
        f"📈 رسوم ({fee_percent}%): {fee_amount} {payment_currency}"
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


# ──────────────────────────────────────────────────────────────────────────────
# Orders list with pagination
# ──────────────────────────────────────────────────────────────────────────────

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
            f"💰 {_format_usdt(order['amount_usdt'])} USDT ({order['network']})\n"
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


# ──────────────────────────────────────────────────────────────────────────────
# Receipt upload flow
# ──────────────────────────────────────────────────────────────────────────────

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
    lang = await _get_user_lang(callback.from_user.id)
    prompt = (
        "📎 أرسل صورة الإيصال للطلب #{} (مثل صورة التحويل من شام كاش):\n\n"
        "💡 تأكد من ظهور جميع البيانات بوضوح:\n"
        "• تاريخ العملية\n"
        "• اسم المرسل ورقم حسابه\n"
        "• اسم المستلم ورقم حسابه\n"
        "• المبلغ"
    ).format(order['order_number']) if lang == 'ar' else (
        "📎 Send receipt image for order #{} (Sham Cash transfer screenshot):\n\n"
        "💡 Make sure all data is clearly visible:\n"
        "• Transaction date\n"
        "• Sender name & account\n"
        "• Recipient name & account\n"
        "• Amount"
    ).format(order['order_number'])

    await callback.message.answer(prompt)
    await state.set_state(ReceiptStates.waiting_receipt)
    await callback.answer()


@router.message(ReceiptStates.waiting_receipt, F.photo)
async def handle_receipt_upload(message: Message, state: FSMContext):
    """Handle receipt photo upload with ShamCash automated verification."""
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
            """SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name,
                      u.shamcash_account, u.language
               FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1""",
            order_id
        )

    if not order:
        await message.answer("❌ الطلب غير موجود.")
        await state.clear()
        return

    lang = order['language'] or 'ar'
    attempt_count = order['receipt_upload_count'] + 1

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
        admin_account = (
            Config.get_shamcash_syp()
            if order['payment_currency'] == 'SYP'
            else Config.get_shamcash_usd()
        )

        verification_result = await ReceiptVerifier.verify_shamcash_receipt(
            image_bytes=image_bytes,
            order_date=order['created_at'],
            customer_name=order['full_name'] or '',
            customer_shamcash_account=order['shamcash_account'] or '',
            admin_name=Config.get_shamcash_name(),
            admin_shamcash_account=admin_account,
            expected_amount=float(order['total_amount']),
            payment_currency=order['payment_currency'],
        )

        logger.info(f"ShamCash verification result: score={verification_result.get('score')}, "
                     f"auto_verified={verification_result.get('auto_verified')}")

    auto_verified = verification_result and verification_result.get('auto_verified', False)
    remaining_attempts = MAX_RECEIPT_ATTEMPTS - attempt_count

    await pool.execute(
        "UPDATE orders SET receipt_photo_id = $1, receipt_upload_count = receipt_upload_count + 1 WHERE id = $2",
        photo_id, order_id
    )

    if auto_verified:
        await pool.execute(
            "UPDATE orders SET status = 'receipt_received' WHERE id = $1",
            order_id
        )

        score = verification_result.get('score', 0)
        score_label = verification_result.get('score_label', '')

        user_msg = (
            f"✅ <b>تم التحقق من الإيصال آلياً!</b>\n\n"
            f"📊 نسبة التطابق: {score}% ({score_label})\n"
            f"📦 جاري إرسال البيانات للإدارة للمراجعة النهائية...\n\n"
            f"🔍 سيتم تأكيد الدفع بعد المراجعة اليدوية."
        ) if lang == 'ar' else (
            f"✅ <b>Receipt auto-verified successfully!</b>\n\n"
            f"📊 Match score: {score}% ({score_label})\n"
            f"📦 Sending data to admin for final review...\n\n"
            f"🔍 Payment will be confirmed after manual review."
        )

        await message.answer(user_msg, parse_mode='HTML')

        await _notify_admins_receipt(
            bot=bot,
            order=order,
            photo_id=photo_id,
            verification_result=verification_result,
            username=message.chat.username or '',
            is_auto_verified=True,
        )

        await state.clear()

    else:
        score = verification_result.get('score', 0) if verification_result else 0
        score_label = verification_result.get('score_label', 'فاشل') if verification_result else 'فاشل'

        if verification_result and verification_result.get('details'):
            fail_details = "\n".join(verification_result['details'])
        else:
            fail_details = "⚠️ لم يتم التعرف على الإيصال كإيصال شام كاش صالح."

        user_msg = (
            f"⚠️ <b>تعذر التحقق من الإيصال آلياً</b>\n"
            f"📊 نسبة التطابق: {score}% ({score_label})\n\n"
            f"{fail_details}\n\n"
        )

        if remaining_attempts > 0:
            user_msg += (
                f"🔄 لديك <b>{remaining_attempts}</b> محاولات متبقية.\n"
                f"يرجى التأكد من:\n"
                f"• وضوح الصورة\n"
                f"• ظهور تاريخ العملية\n"
                f"• ظهور اسم المرسل والمستلم\n"
                f"• ظهور المبلغ المحول\n\n"
                f"📎 يمكنك إعادة رفع الإيصال، أو إرساله للمشرف للمراجعة مباشرة."
            ) if lang == 'ar' else (
                f"🔄 You have <b>{remaining_attempts}</b> attempts remaining.\n"
                f"Please ensure:\n"
                f"• Image is clear\n"
                f"• Transaction date is visible\n"
                f"• Sender & recipient names are visible\n"
                f"• Transfer amount is visible\n\n"
                f"📎 You can re-upload the receipt, or send it directly to admin for review."
            )

            await message.answer(
                user_msg,
                parse_mode='HTML',
                reply_markup=_verification_fail_keyboard(order_id, lang)
            )
            await state.update_data(receipt_order_id=order_id)
        else:
            await pool.execute(
                "UPDATE orders SET status = 'receipt_received' WHERE id = $1",
                order_id
            )

            user_msg += (
                f"❌ لقد استنفذت جميع المحاولات ({MAX_RECEIPT_ATTEMPTS}).\n"
                f"📦 سيتم إرسال الإيصال للإدارة للمراجعة اليدوية."
            ) if lang == 'ar' else (
                f"❌ You have exhausted all attempts ({MAX_RECEIPT_ATTEMPTS}).\n"
                f"📦 The receipt will be forwarded to admin for manual review."
            )

            await message.answer(user_msg, parse_mode='HTML')

            await _notify_admins_receipt(
                bot=bot,
                order=order,
                photo_id=photo_id,
                verification_result=verification_result,
                username=message.chat.username or '',
                is_auto_verified=False,
            )

            await state.clear()


@router.callback_query(F.data.startswith("retry_receipt_"))
async def retry_receipt_upload(callback: CallbackQuery, state: FSMContext):
    """User wants to retry receipt upload after failed verification."""
    order_id = int(callback.data.replace("retry_receipt_", ""))

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

    attempts = order['receipt_upload_count']
    if attempts >= MAX_RECEIPT_ATTEMPTS:
        await callback.answer("لقد استنفذت جميع المحاولات", show_alert=True)
        return

    await state.update_data(receipt_order_id=order_id)
    lang = await _get_user_lang(callback.from_user.id)
    prompt = (
        f"📎 أرسل صورة جديدة للإيصال للطلب #{order['order_number']}\n"
        f"🔄 المحاولة {attempts + 1}/{MAX_RECEIPT_ATTEMPTS}\n\n"
        f"💡 تأكد من وضوح:\n"
        f"• تاريخ العملية — التاريخ والوقت\n"
        f"• اسم المرسل ورقم حسابه\n"
        f"• اسم المستلم ورقم حسابه (شام كاش)\n"
        f"• المبلغ المحول"
    ) if lang == 'ar' else (
        f"📎 Send a new receipt image for order #{order['order_number']}\n"
        f"🔄 Attempt {attempts + 1}/{MAX_RECEIPT_ATTEMPTS}\n\n"
        f"💡 Make sure these are clear:\n"
        f"• Transaction date & time\n"
        f"• Sender name & account\n"
        f"• Recipient name & account (Sham Cash)\n"
        f"• Transfer amount"
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(prompt)
    await state.set_state(ReceiptStates.waiting_receipt)
    await callback.answer()


@router.callback_query(F.data.startswith("manual_review_"))
async def manual_review_after_fail(callback: CallbackQuery, state: FSMContext):
    """Send the failed receipt directly to admins for review."""
    order_id = int(callback.data.replace("manual_review_", ""))

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            """SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name,
                      u.shamcash_account, u.language
               FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1""",
            order_id
        )

    if not order:
        await callback.answer("الطلب غير موجود", show_alert=True)
        return

    if order['status'] != 'waiting_payment':
        await callback.answer("لا يمكن رفع إيصال لهذا الطلب حالياً", show_alert=True)
        return

    lang = order['language'] or 'ar'
    photo_id = order.get('receipt_photo_id')

    await pool.execute(
        "UPDATE orders SET status = 'receipt_received' WHERE id = $1",
        order_id
    )

    bot = Bot(token=Config.BOT_TOKEN)

    user_msg = (
        "👨‍💼 <b>تم إرسال الإيصال للمشرف للمراجعة</b>\n\n"
        f"📦 الطلب: <b>#{order['order_number']}</b>\n"
        "📎 تم استلام الإيصال وسيقوم المشرف بمراجعة بيانات التحويل وتحديث حالة الطلب.\n\n"
        "🔒 لا حاجة لإعادة رفع الإيصال ما لم يطلب منك المشرف ذلك."
    ) if lang == 'ar' else (
        "👨‍💼 <b>Receipt sent to admin for review</b>\n\n"
        f"📦 Order: <b>#{order['order_number']}</b>\n"
        "📎 The receipt has been received. Admin will review the transfer details and update the order status.\n\n"
        "🔒 No need to re-upload the receipt unless admin asks you to."
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(user_msg, parse_mode='HTML')

    await _notify_admins_receipt(
        bot=bot,
        order=order,
        photo_id=photo_id or '',
        verification_result=None,
        username=callback.from_user.username or '',
        is_auto_verified=False,
    )

    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "👨‍💼 <b>طلب مراجعة مباشرة</b>\n"
                "تم إرسال الإيصال للمشرف بعد تعذر التحقق الآلي.\n\n"
                f"📦 الطلب: #{order['order_number']}\n"
                f"👤 العميل: {html.escape(order['full_name'] or 'N/A')}\n"
                "🔎 الإجراء المطلوب: مراجعة الإيصال وتحديد حالة الدفع.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    await state.clear()
    await callback.answer()


@router.message(ReceiptStates.waiting_receipt, ~F.photo)
async def handle_receipt_non_photo(message: Message, state: FSMContext):
    """Handle non-photo message during receipt upload."""
    data = await state.get_data()
    order_id = data.get('receipt_order_id')
    lang = await _get_user_lang(message.from_user.id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id) if order_id else None

    remaining = MAX_RECEIPT_ATTEMPTS
    if order:
        remaining = MAX_RECEIPT_ATTEMPTS - order['receipt_upload_count']

    msg = (
        f"❌ يرجى إرسال صورة (وليس نصاً).\n\n"
        f"📎 أرسل صورة واضحة لإيصال تحويل شام كاش.\n"
        f"🔄 المحاولات المتبقية: {remaining}"
    ) if lang == 'ar' else (
        f"❌ Please send an image (not text).\n\n"
        f"📎 Send a clear image of the Sham Cash transfer receipt.\n"
        f"🔄 Remaining attempts: {remaining}"
    )

    await message.answer(msg)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _get_user_lang(telegram_id: int) -> str:
    """Fetch user language from DB."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
            if user:
                return user['language']
    except Exception:
        pass
    return 'ar'
