"""Canonical customer receipt processing service.

This module contains the receipt upload implementation without registering any
Telegram handlers. Router ownership remains in the receipt policy modules.
"""
import html
import logging

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from database import get_pool
from keyboards.inline import order_admin_keyboard
from services.formatters import money, rate, usdt
from services.order_state_service import InvalidOrderTransition, transition_order
from services.receipt_verifier import ReceiptVerifier

logger = logging.getLogger(__name__)
MAX_RECEIPT_ATTEMPTS = 3


async def notify_admins_receipt(
    bot: Bot,
    order: dict,
    photo_id: str,
    verification_result: dict | None,
    username: str,
    is_auto_verified: bool,
) -> None:
    """Send a receipt and its verification summary to every configured admin."""
    score = verification_result.get("score", 0) if verification_result else 0
    score_label = verification_result.get("score_label", "فاشل") if verification_result else "فاشل"
    details = verification_result.get("details", []) if verification_result else []
    verification_block = (
        "━━━ 🤖 التحقق الآلي من شام كاش ━━━\n"
        f"{'✅' if is_auto_verified else '⚠️'} نسبة الثقة: <b>{score}%</b> ({html.escape(str(score_label))})\n"
        + ("\n".join(details) + "\n" if details else "⚠️ لا توجد نتيجة تحقق آلي متاحة.\n")
    )
    currency = html.escape(order.get("payment_currency") or "USD")
    admin_text = (
        "📎 <b>إيصال دفع — مراجعة</b>\n\n"
        f"📦 الطلب: <b>#{html.escape(order['order_number'])}</b>\n"
        f"💰 الكمية: <b>{usdt(order['amount_usdt'])} USDT</b>\n"
        f"💱 سعر الصرف: <b>{rate(order.get('exchange_rate'))}</b> {currency}\n"
        f"💵 الأساسي: <b>{money(order.get('base_amount'))}</b> {currency}\n"
        f"📈 الرسوم: <b>{money(order.get('fee_amount'))}</b> {currency}\n"
        f"💵 الإجمالي: <b>{money(order['total_amount'])}</b> {currency}\n"
        f"🌐 الشبكة: {html.escape(order.get('network') or '')}\n"
        f"📍 المحفظة: <code>{html.escape(order.get('wallet_address') or '')}</code>\n"
        f"👤 العميل: <b>{html.escape(order.get('full_name') or 'N/A')}</b>\n"
        f"🆔 <code>{order.get('user_telegram_id') or ''}</code>\n"
        f"📱 @{html.escape(username or 'N/A')}\n"
        f"🏦 ShamCash: <code>{html.escape(order.get('shamcash_account') or 'N/A')}</code>\n\n"
        f"{verification_block}"
    )
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=order_admin_keyboard(order["id"], "receipt_received"),
                parse_mode="HTML",
            )
            if photo_id:
                await bot.send_photo(
                    admin_id,
                    photo_id,
                    caption=f"📸 إيصال الدفع للطلب #{order['order_number']}",
                )
        except Exception:
            logger.exception(
                "Failed to notify admin %s about receipt %s",
                admin_id,
                order["id"],
            )


async def handle_receipt_upload(message: Message, state: FSMContext) -> None:
    """Process one customer receipt upload through the canonical order graph."""
    data = await state.get_data()
    order_id = data.get("receipt_order_id")
    if not order_id:
        await message.answer("❌ حدث خطأ. يرجى بدء رفع الإيصال من الطلب مرة أخرى.")
        await state.clear()
        return

    if not message.photo:
        await message.answer("❌ يرجى إرسال صورة الإيصال.")
        return

    photo_id = message.photo[-1].file_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            """SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name,
                      u.shamcash_account, u.language
               FROM orders o JOIN users u ON o.user_id = u.id
               WHERE o.id = $1 AND u.telegram_id = $2""",
            order_id,
            message.from_user.id,
        )
    if not order:
        await message.answer("❌ الطلب غير موجود أو لا تملك هذا الطلب.")
        await state.clear()
        return
    if order["status"] != "waiting_payment":
        await message.answer("❌ لا يمكن رفع إيصال لهذا الطلب حالياً.")
        await state.clear()
        return

    attempt_count = int(order["receipt_upload_count"] or 0) + 1
    if attempt_count > MAX_RECEIPT_ATTEMPTS:
        await message.answer("❌ تم استنفاد محاولات رفع الإيصال لهذا الطلب.")
        await state.clear()
        return

    bot = Bot(token=Config.BOT_TOKEN)
    try:
        image_bytes = None
        try:
            file_info = await bot.get_file(photo_id)
            image_file = await bot.download_file(file_info.file_path)
            image_bytes = image_file.read()
        except Exception:
            logger.exception("Failed to download receipt image for order %s", order_id)

        payment_currency = order["payment_currency"] or "USD"
        admin_account = (
            Config.get_shamcash_syp()
            if payment_currency in ("SYP", "NEW.SYP")
            else Config.get_shamcash_usd()
        )
        verification_result = None
        if image_bytes:
            verification_result = await ReceiptVerifier.verify_shamcash_receipt(
                image_bytes=image_bytes,
                order_date=order["created_at"],
                customer_name=order["full_name"] or "",
                customer_shamcash_account=order["shamcash_account"] or "",
                admin_name=Config.get_shamcash_name(),
                admin_shamcash_account=admin_account,
                expected_amount=float(order["total_amount"]),
                payment_currency=payment_currency,
            )

        auto_verified = bool(
            verification_result and verification_result.get("auto_verified")
        )
        remaining_attempts = MAX_RECEIPT_ATTEMPTS - attempt_count

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET receipt_photo_id = $1, receipt_upload_count = $2 WHERE id = $3",
                photo_id,
                attempt_count,
                order_id,
            )
            if auto_verified or remaining_attempts <= 0:
                try:
                    updated = await transition_order(
                        conn,
                        order_id,
                        "receipt_received",
                        updates={
                            "receipt_photo_id": photo_id,
                            "receipt_upload_count": attempt_count,
                        },
                    )
                except InvalidOrderTransition:
                    await message.answer(
                        "⚠️ تغيرت حالة الطلب أثناء معالجة الإيصال. افتح طلباتك للتحقق."
                    )
                    await state.clear()
                    return
            else:
                updated = await conn.fetchrow(
                    "SELECT * FROM orders WHERE id = $1",
                    order_id,
                )

        if auto_verified:
            score = verification_result.get("score", 0)
            label = verification_result.get("score_label", "")
            await message.answer(
                f"✅ <b>تم التحقق من الإيصال آلياً.</b>\n\n"
                f"📊 نسبة التطابق: <b>{score}%</b> ({html.escape(str(label))})\n"
                "📦 تم إرسال الإيصال للمراجعة النهائية من الإدارة.",
                parse_mode="HTML",
            )
            await notify_admins_receipt(
                bot,
                dict(updated),
                photo_id,
                verification_result,
                message.from_user.username or "",
                True,
            )
            await state.clear()
            return

        if remaining_attempts <= 0:
            await message.answer(
                "❌ <b>تم استنفاد محاولات التحقق الآلي.</b>\n\n"
                "تم إرسال الإيصال إلى الإدارة للمراجعة اليدوية.",
                parse_mode="HTML",
            )
            await notify_admins_receipt(
                bot,
                dict(updated),
                photo_id,
                verification_result,
                message.from_user.username or "",
                False,
            )
            await state.clear()
            return

        score = verification_result.get("score", 0) if verification_result else 0
        label = (
            verification_result.get("score_label", "فاشل")
            if verification_result
            else "فاشل"
        )
        await message.answer(
            f"⚠️ <b>تعذر التحقق من الإيصال آلياً.</b>\n\n"
            f"📊 نسبة التطابق: <b>{score}%</b> ({html.escape(str(label))})\n\n"
            f"🔄 لديك <b>{remaining_attempts}</b> محاولات متبقية. "
            "يمكنك إعادة الرفع أو اختيار المراجعة اليدوية.",
            parse_mode="HTML",
        )
        await state.update_data(receipt_order_id=order_id)
    finally:
        await bot.session.close()
