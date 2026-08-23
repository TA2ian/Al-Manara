"""Canonical customer receipt document policy with image/PDF OCR validation."""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from database import get_pool
from keyboards.inline import order_admin_keyboard
from services.formatters import money, usdt
from services.order_state_service import InvalidOrderTransition, transition_order
from services.receipt_media import normalize_receipt_media
from services.receipt_processing_lock import serialize_receipt_handler
from services.receipt_verifier import ReceiptVerifier
from states import ReceiptStates

logger = logging.getLogger(__name__)
router = Router()
MAX_RECEIPT_ATTEMPTS = 3


async def _lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


async def _load_owned_order(order_id: int, telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name,
                      u.shamcash_account, u.language
               FROM orders o JOIN users u ON o.user_id = u.id
               WHERE o.id = $1 AND u.telegram_id = $2""",
            order_id, telegram_id,
        )


@router.callback_query(F.data.startswith("upload_receipt_"))
async def start_exported_receipt_upload(callback, state: FSMContext):
    order_id = int(callback.data.replace("upload_receipt_", ""))
    order = await _load_owned_order(order_id, callback.from_user.id)
    lang = await _lang(callback.from_user.id)
    if not order:
        await callback.answer("الطلب غير موجود" if lang == "ar" else "Order not found", show_alert=True)
        return
    if order["status"] != "waiting_payment":
        await callback.answer("لا يمكن رفع إثبات لهذا الطلب حالياً" if lang == "ar" else "This order is not awaiting payment proof", show_alert=True)
        return
    if int(order["receipt_upload_count"] or 0) >= MAX_RECEIPT_ATTEMPTS:
        await callback.answer("❌ استنفدت محاولات رفع الإثبات" if lang == "ar" else "❌ Receipt attempts exhausted", show_alert=True)
        return
    await state.update_data(receipt_order_id=order_id)
    prompt = (
        f"📎 <b>إرسال إثبات الدفع — الطلب #{order['order_number']}</b>\n\n"
        "أرسل صورة JPG/PNG/WebP أو ملف PDF مُصدّراً من ShamCash. سيتم التحقق من نوع الملف وقراءته آلياً عبر OCR قبل إرساله للمراجعة.\n\n"
        "⚠️ الحد الأقصى 12 MB، وPDF يجب ألا يتجاوز 3 صفحات."
        if lang == "ar" else
        f"📎 <b>Payment proof — order #{order['order_number']}</b>\n\n"
        "Send a JPG/PNG/WebP image or a PDF exported from ShamCash. The file type will be validated and its contents checked with OCR before review.\n\n"
        "⚠️ Maximum 12 MB; PDFs may contain up to 3 pages."
    )
    await callback.message.answer(prompt, parse_mode="HTML")
    await state.set_state(ReceiptStates.waiting_receipt)
    await callback.answer()


@router.message(ReceiptStates.waiting_receipt, F.document)
@serialize_receipt_handler
async def handle_exported_receipt_document(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("receipt_order_id")
    lang = await _lang(message.from_user.id)
    if not order_id:
        await message.answer("❌ لم يتم العثور على الطلب الحالي." if lang == "ar" else "❌ No active receipt request was found.")
        await state.clear()
        return

    order = await _load_owned_order(order_id, message.from_user.id)
    if not order or order["status"] != "waiting_payment":
        await message.answer("❌ الطلب غير موجود أو لم يعد بانتظار إثبات الدفع." if lang == "ar" else "❌ Order not found or no longer awaiting payment proof.")
        await state.clear()
        return

    attempt_count = int(order["receipt_upload_count"] or 0) + 1
    if attempt_count > MAX_RECEIPT_ATTEMPTS:
        await message.answer("❌ تم استنفاد محاولات رفع الإثبات." if lang == "ar" else "❌ Receipt upload attempts exhausted.")
        await state.clear()
        return

    document = message.document
    file_id = document.file_id
    file_name = document.file_name or "payment_proof"
    mime_type = document.mime_type or "application/octet-stream"
    bot = Bot(token=Config.BOT_TOKEN)
    try:
        try:
            file_info = await bot.get_file(file_id)
            downloaded = await bot.download_file(file_info.file_path)
            normalized, _ = normalize_receipt_media(downloaded.read(), mime_type, file_name)
        except ValueError as exc:
            await message.answer(f"❌ <b>نوع الملف غير مقبول أو الملف تالف.</b>\n\n{html.escape(str(exc))}", parse_mode="HTML")
            return
        except Exception:
            logger.exception("Failed to download receipt document for order %s", order_id)
            await message.answer("❌ تعذر قراءة الملف. أعد إرساله بصيغة JPG/PNG/WebP أو PDF صالح.")
            return

        payment_currency = order["payment_currency"] or "USD"
        admin_account = Config.get_shamcash_syp() if payment_currency in ("SYP", "NEW.SYP") else Config.get_shamcash_usd()
        verification_result = await ReceiptVerifier.verify_shamcash_receipt(
            image_bytes=normalized,
            order_date=order["created_at"],
            customer_name=order["full_name"] or "",
            customer_shamcash_account=order["shamcash_account"] or "",
            admin_name=Config.get_shamcash_name(),
            admin_shamcash_account=admin_account,
            expected_amount=float(order["total_amount"]),
            payment_currency=payment_currency,
        )
        score = int(verification_result.get("score", 0))
        auto_verified = bool(verification_result.get("auto_verified"))
        remaining_attempts = MAX_RECEIPT_ATTEMPTS - attempt_count

        pool = await get_pool()
        async with pool.acquire() as conn:
            if auto_verified or remaining_attempts <= 0:
                try:
                    updated = await transition_order(conn, order_id, "receipt_received", updates={"receipt_photo_id": file_id, "receipt_upload_count": attempt_count})
                except InvalidOrderTransition:
                    await message.answer("⚠️ تغيرت حالة الطلب أثناء المعالجة. افتح طلباتك للتحقق.")
                    await state.clear()
                    return
            else:
                await conn.execute("UPDATE orders SET receipt_photo_id=$1, receipt_upload_count=$2 WHERE id=$3", file_id, attempt_count, order_id)
                updated = await conn.fetchrow("SELECT * FROM orders WHERE id=$1", order_id)

        if auto_verified:
            await message.answer(f"✅ <b>تمت قراءة الإيصال والتحقق منه آلياً.</b>\n\n📊 نسبة المطابقة: <b>{score}%</b>\n📦 أُرسل للمراجعة النهائية من الإدارة.", parse_mode="HTML")
        elif remaining_attempts <= 0:
            await message.answer("❌ <b>تعذر التحقق آلياً بعد استنفاد المحاولات.</b>\n\nتم إرسال الإثبات للإدارة للمراجعة اليدوية.", parse_mode="HTML")
        else:
            await message.answer(f"⚠️ <b>تمت قراءة الملف لكن لم يكتمل التطابق.</b>\n\n📊 نسبة المطابقة: <b>{score}%</b>\n🔄 المحاولات المتبقية: <b>{remaining_attempts}</b>.", parse_mode="HTML")

        admin_text = (
            "📎 <b>إثبات دفع — تحقق OCR</b>\n\n"
            f"📦 الطلب: <b>#{order['order_number']}</b>\n"
            f"💰 المبلغ: <b>{usdt(order['amount_usdt'])} USDT</b> → {html.escape(order['network'])}\n"
            f"💳 المطلوب: <b>{money(order['total_amount'])} {html.escape(order['payment_currency'])}</b>\n"
            f"👤 العميل: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
            f"📄 الملف: <code>{html.escape(file_name)}</code>\n"
            f"🧾 النوع: <code>{html.escape(mime_type)}</code>\n"
            f"🤖 OCR: <b>{score}%</b> — {html.escape(verification_result.get('score_label', 'فاشل'))}\n\n"
            + "\n".join(verification_result.get("details", []))
        )
        for admin_id in Config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, reply_markup=order_admin_keyboard(order_id, "receipt_received"), parse_mode="HTML")
                await bot.send_document(admin_id, file_id, caption=f"📄 إثبات الدفع الأصلي — #{order['order_number']}")
            except Exception:
                logger.exception("Failed to notify admin %s about receipt %s", admin_id, order_id)

        if remaining_attempts <= 0 or auto_verified:
            await state.clear()
    finally:
        await bot.session.close()


@router.message(ReceiptStates.waiting_receipt)
async def reject_unsupported_receipt_document(message: Message):
    lang = await _lang(message.from_user.id)
    await message.answer(
        "❌ صيغة الإثبات غير مدعومة. أرسل JPG أو PNG أو WebP أو PDF صالحاً من ShamCash."
        if lang == "ar" else
        "❌ Unsupported proof format. Send a valid ShamCash JPG, PNG, WebP, or PDF."
    )
