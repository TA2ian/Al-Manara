"""Canonical receipt submission workflow for customer photo and document uploads."""
from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from database import get_pool
from keyboards.inline import manual_receipt_review_keyboard, order_admin_keyboard
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


async def _start_progress(message: Message, lang: str) -> tuple[Message, dict, asyncio.Task]:
    state = {"label": "استلام الملف", "percent": 10}
    started = time.monotonic()
    frames = ("▰▱▱▱▱", "▰▰▱▱▱", "▰▰▰▱▱", "▰▰▰▰▱", "▰▰▰▰▰")

    def render() -> str:
        elapsed = int(time.monotonic() - started)
        frame = frames[elapsed % len(frames)]
        if lang == "ar":
            return (
                "⏳ <b>جارٍ فحص إثبات الدفع</b>\n\n"
                f"{frame} <b>{state['percent']}%</b>\n"
                f"🔎 الحالة: <b>{html.escape(state['label'])}</b>\n"
                f"⏱ الزمن المنقضي: <b>{elapsed} ثانية</b>\n\n"
                "لا ترسل ملفاً آخر حتى تظهر النتيجة."
            )
        return (
            "⏳ <b>Checking your payment proof</b>\n\n"
            f"{frame} <b>{state['percent']}%</b>\n"
            f"🔎 Status: <b>{html.escape(state['label'])}</b>\n"
            f"⏱ Elapsed: <b>{elapsed} seconds</b>\n\n"
            "Please do not send another file until the result appears."
        )

    progress = await message.answer(render(), parse_mode="HTML")

    async def ticker() -> None:
        while True:
            await asyncio.sleep(1)
            try:
                await progress.edit_text(render(), parse_mode="HTML")
            except TelegramBadRequest:
                return
            except Exception:
                logger.debug("Receipt progress update failed", exc_info=True)

    task = asyncio.create_task(ticker())
    return progress, state, task


async def _set_progress_stage(progress: Message, state: dict, label: str, percent: int) -> None:
    state["label"] = label
    state["percent"] = percent
    try:
        elapsed = int(time.monotonic() - state.get("started", time.monotonic()))
        await progress.edit_text(
            f"⏳ <b>جارٍ فحص إثبات الدفع</b>\n\n"
            f"▰{'▰' * max(0, min(4, percent // 20 - 1))}{'▱' * max(0, 4 - min(4, percent // 20 - 1))} <b>{percent}%</b>\n"
            f"🔎 الحالة: <b>{html.escape(label)}</b>\n"
            f"⏱ الزمن المنقضي: <b>{elapsed} ثانية</b>\n\n"
            "لا ترسل ملفاً آخر حتى تظهر النتيجة.",
            parse_mode="HTML",
        )
    except Exception:
        logger.debug("Receipt progress stage update failed", exc_info=True)


def _customer_result_message(
    verification_result: dict,
    remaining_attempts: int,
    auto_verified: bool,
    order_id: int,
) -> tuple[str, str, Any | None]:
    score = int(verification_result.get("score", 0))
    label = html.escape(str(verification_result.get("score_label", "فاشل")))
    if auto_verified:
        return (
            f"✅ <b>تم التحقق من الإيصال آلياً.</b>\n\n"
            f"📊 نسبة التطابق: <b>{score}%</b> ({label})\n"
            "📦 تم إرسال الإيصال للمراجعة النهائية من الإدارة.",
            "HTML",
            None,
        )
    if remaining_attempts <= 0:
        return (
            "❌ <b>تم استنفاد محاولات التحقق الآلي.</b>\n\n"
            "📨 تم إرسال آخر إيصال إلى الإدارة للمراجعة اليدوية.",
            "HTML",
            None,
        )
    return (
        f"⚠️ <b>تعذر التحقق من الإيصال آلياً.</b>\n\n"
        f"📊 نسبة التطابق: <b>{score}%</b> ({label})\n\n"
        f"🔄 لديك <b>{remaining_attempts}</b> محاولات متبقية.\n"
        "يمكنك إعادة الرفع، أو طلب مراجعة هذا الإيصال يدوياً من الإدارة.",
        "HTML",
        manual_receipt_review_keyboard(order_id),
    )


async def notify_admins_receipt(
    bot: Bot,
    order: dict,
    file_id: str,
    file_name: str,
    verification_result: dict | None,
    username: str,
    is_auto_verified: bool,
    is_document: bool | None,
    manual_review_requested: bool = False,
) -> None:
    score = verification_result.get("score", 0) if verification_result else 0
    score_label = verification_result.get("score_label", "فاشل") if verification_result else "فاشل"
    details = verification_result.get("details", []) if verification_result else []
    verification_block = (
        "━━━ 🤖 التحقق الآلي من شام كاش ━━━\n"
        f"{'✅' if is_auto_verified else '⚠️'} نسبة الثقة: <b>{score}%</b> ({html.escape(str(score_label))})\n"
        + ("\n".join(details) + "\n" if details else "⚠️ لا توجد نتيجة تحقق آلي متاحة.\n")
    )
    request_block = "📨 <b>طلب العميل مراجعة يدوية لهذا الإيصال.</b>\n\n" if manual_review_requested else ""
    currency = html.escape(order.get("payment_currency") or "USD")
    admin_text = (
        "📎 <b>إيصال دفع — مراجعة</b>\n\n"
        f"{request_block}"
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
            if is_document is True:
                await bot.send_document(
                    admin_id,
                    file_id,
                    caption=f"📄 إثبات الدفع الأصلي — #{order['order_number']} — {file_name}",
                )
            elif is_document is False:
                await bot.send_photo(
                    admin_id,
                    file_id,
                    caption=f"📸 إيصال الدفع للطلب #{order['order_number']}",
                )
            else:
                try:
                    await bot.send_document(
                        admin_id,
                        file_id,
                        caption=f"📄 إثبات الدفع — #{order['order_number']} — {file_name}",
                    )
                except Exception:
                    await bot.send_photo(
                        admin_id,
                        file_id,
                        caption=f"📸 إيصال الدفع للطلب #{order['order_number']}",
                    )
        except Exception:
            logger.exception("Failed to notify admin %s about receipt %s", admin_id, order["id"])


async def request_manual_receipt_review(bot: Bot, order_id: int, telegram_id: int, username: str) -> tuple[bool, str]:
    """Transition the customer's latest failed receipt to manual review exactly once."""
    order = await _load_owned_order(order_id, telegram_id)
    if not order:
        return False, "❌ الطلب غير موجود أو لا تملك هذا الطلب."
    if order["status"] != "waiting_payment":
        return False, "❌ لم يعد هذا الطلب بانتظار إثبات دفع جديد."
    file_id = order["receipt_photo_id"]
    if not file_id:
        return False, "❌ لا يوجد إيصال محفوظ لإرساله إلى الإدارة."

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            updated = await transition_order(
                conn,
                order_id,
                "receipt_received",
                updates={"receipt_photo_id": file_id},
            )
        except InvalidOrderTransition:
            return False, "❌ تغيرت حالة الطلب أثناء طلب المراجعة."

    if updated is None:
        return False, "❌ تعذر تثبيت طلب المراجعة اليدوية."

    bot_message_type = None
    await notify_admins_receipt(
        bot=bot,
        order=dict(updated),
        file_id=file_id,
        file_name="payment_proof",
        verification_result=None,
        username=username,
        is_auto_verified=False,
        is_document=bot_message_type,
        manual_review_requested=True,
    )
    return True, "📨 تم إرسال الإيصال إلى الإدارة للمراجعة اليدوية. سيتم إشعارك عند اتخاذ القرار."


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
            await message.answer("⏳ جارٍ التحقق من إيصال آخر لهذا الطلب. انتظر النتيجة قبل إرسال إثبات آخر.")
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

        progress = None
        progress_state = None
        progress_task = None
        try:
            lang = order["language"] if order["language"] in ("ar", "en") else "ar"
            progress, progress_state, progress_task = await _start_progress(message, lang)
            progress_state["started"] = time.monotonic()

            try:
                await _set_progress_stage(
                    progress,
                    progress_state,
                    "تجهيز الملف للتحليل" if lang == "ar" else "Preparing file",
                    30,
                )
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

            await _set_progress_stage(
                progress,
                progress_state,
                "تحليل الإيصال عبر OCR" if lang == "ar" else "Running OCR analysis",
                70,
            )
            verification_result = await _verify_receipt(order, image_bytes)
            await _set_progress_stage(
                progress,
                progress_state,
                "مطابقة البيانات وإعداد النتيجة" if lang == "ar" else "Matching data and preparing result",
                90,
            )
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
                await message.answer("⚠️ تغيرت حالة الطلب أثناء معالجة الإيصال. افتح طلباتك للتحقق.")
                await state.clear()
                return

            text, parse_mode, keyboard = _customer_result_message(
                verification_result,
                remaining_attempts,
                auto_verified,
                int(order_id),
            )
            await message.answer(text, parse_mode=parse_mode, reply_markup=keyboard)

            if auto_verified or remaining_attempts <= 0:
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
        finally:
            if progress_task:
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.debug("Receipt progress task cleanup failed", exc_info=True)
            if progress:
                try:
                    await progress.delete()
                except Exception:
                    logger.debug("Receipt progress message could not be deleted", exc_info=True)
