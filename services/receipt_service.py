"""Canonical receipt submission workflow for customer photo and document uploads."""
from __future__ import annotations

import html
import logging
from typing import Any

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from database import get_pool
from keyboards.inline import order_admin_keyboard
from services.formatters import money, rate, usdt
from services.order_state_service import InvalidOrderTransition, transition_order
from services.receipt_media import normalize_receipt_media
from services.receipt_processing_lock import receipt_processing_lock
from services.receipt_verifier import ReceiptVerifier

logger = logging.getLogger(__name__)
MAX_RECEIPT_ATTEMPTS = 3


async def _load_owned_order(order_id: int, telegram_id: int) -> Any | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name,
                   u.shamcash_account, u.language
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE o.id = $1 AND u.telegram_id = $2
            """,
            order_id,
            telegram_id,
        )


async def _download_submission(bot: Bot, message: Message) -> tuple[str, str, bytes, str]:
    if message.photo:
        file_id = message.photo[-1].file_id
        file_name = "receipt.jpg"
        mime_type = "image/jpeg"
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "payment_proof"
        mime_type = message.document.mime_type or "application/octet-stream"
    else:
        raise ValueError("unsupported receipt message type")

    file_info = await bot.get_file(file_id)
    downloaded = await bot.download_file(file_info.file_path)
    normalized, normalized_mime = normalize_receipt_media(
        downloaded.read(),
        mime_type,
        file_name,
    )
    return file_id, file_name, normalized, normalized_mime


async def _verify_receipt(order: Any, image_bytes: bytes) -> dict:
    payment_currency = order["payment_currency"] or "USD"
    admin_account = (
        Config.get_shamcash_syp()
        if payment_currency in ("SYP", "NEW.SYP")
        else Config.get_shamcash_usd()
    )
    return await ReceiptVerifier.verify_shamcash_receipt(
        image_bytes=image_bytes,
        order_date=order["created_at"],
        customer_name=order["full_name"] or "",
        customer_shamcash_account=order["shamcash_account"] or "",
        admin_name=Config.get_shamcash_name(),
        admin_shamcash_account=admin_account,
        expected_amount=float(order["total_amount"]),
        payment_currency=payment_currency,
    )


async def _persist_receipt(
    order_id: int,
    file_id: str,
    attempt_count: int,
    auto_verified: bool,
    remaining_attempts: int,
) -> Any:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if auto_verified or remaining_attempts <= 0:
            try:
                return await transition_order(
                    conn,
                    order_id,
                    "receipt_received",
                    updates={
                        "receipt_photo_id": file_id,
                        "receipt_upload_count": attempt_count,
                    },
                )
            except InvalidOrderTransition:
                return None

        await conn.execute(
            """
            UPDATE orders
            SET receipt_photo_id = $1, receipt_upload_count = $2
            WHERE id = $3
            """,
            file_id,
            attempt_count,
            order_id,
        )
        return await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)


def _customer_result_message(
    verification_result: dict,
    remaining_attempts: int,
    auto_verified: bool,
) -> tuple[str, str]:
    score = int(verification_result.get("score", 0))
    label = html.escape(str(verification_result.get("score_label", "فاشل")))
    if auto_verified:
        return (
            f"✅ <b>تم التحقق من الإيصال آلياً.</b>\n\n"
            f"📊 نسبة التطابق: <b>{score}%</b> ({label})\n"
            "📦 تم إرسال الإيصال للمراجعة النهائية من الإدارة.",
            "HTML",
        )
    if remaining_attempts <= 0:
        return (
            "❌ <b>تم استنفاد محاولات التحقق الآلي.</b>\n\n"
            "تم إرسال الإيصال إلى الإدارة للمراجعة اليدوية.",
            "HTML",
        )
    return (
        f"⚠️ <b>تعذر التحقق من الإيصال آلياً.</b>\n\n"
        f"📊 نسبة التطابق: <b>{score}%</b> ({label})\n\n"
        f"🔄 لديك <b>{remaining_attempts}</b> محاولات متبقية. يمكنك إعادة الرفع أو اختيار المراجعة اليدوية.",
        "HTML",
    )


async def notify_admins_receipt(
    bot: Bot,
    order: dict,
    file_id: str,
    file_name: str,
    verification_result: dict | None,
    username: str,
    is_auto_verified: bool,
    is_document: bool,
) -> None:
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
            if is_document:
                await bot.send_document(
                    admin_id,
                    file_id,
                    caption=f"📄 إثبات الدفع الأصلي — #{order['order_number']} — {file_name}",
                )
            else:
                await bot.send_photo(
                    admin_id,
                    file_id,
                    caption=f"📸 إيصال الدفع للطلب #{order['order_number']}",
                )
        except Exception:
            logger.exception(
                "Failed to notify admin %s about receipt %s",
                admin_id,
                order["id"],
            )


async def handle_receipt_upload(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = data.get("receipt_order_id")
    if not order_id:
        await message.answer("❌ حدث خطأ. يرجى بدء رفع الإيصال من الطلب مرة أخرى.")
        await state.clear()
        return

    if not message.photo and not message.document:
        await message.answer("❌ يرجى إرسال صورة أو ملف PDF للإيصال.")
        return

    order = await _load_owned_order(int(order_id), message.from_user.id)
    if not order:
        await message.answer("❌ الطلب غير موجود أو لا تملك هذا الطلب.")
        await state.clear()
        return
    if order["status"] != "waiting_payment":
        await message.answer("❌ لا يمكن رفع إيصال لهذا الطلب حالياً.")
        await state.clear()
        return

    async with receipt_processing_lock(int(order_id)) as acquired:
        if not acquired:
            await message.answer(
                "⏳ جارٍ التحقق من إيصال آخر لهذا الطلب. انتظر النتيجة قبل إرسال إثبات آخر."
            )
            return

        attempt_count = int(order["receipt_upload_count"] or 0) + 1
        if attempt_count > MAX_RECEIPT_ATTEMPTS:
            await message.answer("❌ تم استنفاد محاولات رفع الإيصال لهذا الطلب.")
            await state.clear()
            return

        bot = message.bot
        if bot is None:
            logger.error("Receipt upload received without an attached Telegram bot")
            await message.answer("❌ تعذر معالجة الإيصال حالياً. حاول مرة أخرى.")
            return

        try:
            try:
                file_id, file_name, image_bytes, _ = await _download_submission(bot, message)
            except ValueError as exc:
                await message.answer(
                    f"❌ <b>ملف الإيصال غير صالح أو غير مدعوم.</b>\n\n{html.escape(str(exc))}",
                    parse_mode="HTML",
                )
                return
            except Exception:
                logger.exception("Failed to download or normalize receipt for order %s", order_id)
                await message.answer("❌ تعذر قراءة الإيصال. أعد إرساله بصورة أو PDF صالح.")
                return

            verification_result = await _verify_receipt(order, image_bytes)
            auto_verified = bool(verification_result.get("auto_verified"))
            remaining_attempts = MAX_RECEIPT_ATTEMPTS - attempt_count
            updated = await _persist_receipt(
                int(order_id),
                file_id,
                attempt_count,
                auto_verified,
                remaining_attempts,
            )
            if updated is None:
                await message.answer(
                    "⚠️ تغيرت حالة الطلب أثناء معالجة الإيصال. افتح طلباتك للتحقق."
                )
                await state.clear()
                return

            text, parse_mode = _customer_result_message(
                verification_result,
                remaining_attempts,
                auto_verified,
            )
            await message.answer(text, parse_mode=parse_mode)

            await notify_admins_receipt(
                bot=bot,
                order=dict(updated),
                file_id=file_id,
                file_name=file_name,
                verification_result=verification_result,
                username=message.from_user.username or "",
                is_auto_verified=auto_verified,
                is_document=bool(message.document),
            )

            if auto_verified or remaining_attempts <= 0:
                await state.clear()
            else:
                await state.update_data(receipt_order_id=int(order_id))
        except Exception:
            logger.exception("Unexpected receipt processing failure for order %s", order_id)
            await message.answer("❌ تعذر إكمال معالجة الإيصال. حاول مرة أخرى.")
