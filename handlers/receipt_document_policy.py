"""Customer receipt upload and manual-review entrypoints."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import get_pool
from services.receipt_media import detect_receipt_media_type
from services.receipt_service import (
    MAX_RECEIPT_ATTEMPTS,
    handle_receipt_upload,
    request_manual_receipt_review,
)
from states import ReceiptStates

router = Router()


async def _lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
    return row["language"] if row and row["language"] in ("ar", "en") else "ar"


async def _load_owned_order(order_id: int, telegram_id: int):
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


@router.callback_query(F.data.startswith("upload_receipt_"))
async def start_receipt_upload(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.removeprefix("upload_receipt_"))
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
        "أرسل لقطة شاشة واضحة لإيصال الدفع بصيغة JPG أو PNG أو WebP. سيتم ضغط نسخة مخصصة للتحليل قبل OCR، بينما يبقى الإثبات الأصلي كما أرسلته للمراجعة.\n\n"
        "📄 إذا كان لديك PDF من ShamCash: افتحه، اعرض إيصال الدفع بوضوح، التقط Screenshot وأرسل الصورة بدلاً من ملف PDF. لا يتم تحليل محتوى PDF آلياً.\n\n"
        "⚠️ الحد الأقصى لحجم الملف 12 MB."
        if lang == "ar"
        else
        f"📎 <b>Payment proof — order #{order['order_number']}</b>\n\n"
        "Send a clear JPG, PNG, or WebP screenshot of the payment receipt. A compressed OCR working copy will be created for analysis while your original proof remains available for review.\n\n"
        "📄 If you have a ShamCash PDF, open it, display the receipt clearly, take a screenshot, and send the image instead. PDF contents are not processed automatically.\n\n"
        "⚠️ Maximum file size: 12 MB."
    )
    await callback.message.answer(prompt, parse_mode="HTML")
    await state.set_state(ReceiptStates.waiting_receipt)
    await callback.answer()


@router.callback_query(F.data.startswith("manual_receipt_review_"))
async def request_manual_review(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.removeprefix("manual_receipt_review_"))
    lang = await _lang(callback.from_user.id)
    success, text = await request_manual_receipt_review(
        bot=callback.bot,
        order_id=order_id,
        telegram_id=callback.from_user.id,
        username=callback.from_user.username or "",
    )
    if success:
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(text if lang == "ar" else "📨 The receipt was sent to administration for manual review. You will be notified when a decision is made.")
        await callback.answer("تم الإرسال" if lang == "ar" else "Sent")
        return
    await callback.answer(text if lang == "ar" else "Manual review request could not be completed.", show_alert=True)


@router.message(ReceiptStates.waiting_receipt, F.document)
async def handle_receipt_document(message: Message, state: FSMContext):
    mime_type = message.document.mime_type or ""
    file_name = message.document.file_name or ""
    if detect_receipt_media_type(mime_type, file_name) == "pdf":
        lang = await _lang(message.from_user.id)
        await message.answer(
            "📄 <b>تم اكتشاف ملف PDF.</b>\n\nلا يتم تحليل محتوى PDF عبر OCR. افتح الملف، اعرض صفحة إيصال الدفع بوضوح، التقط Screenshot وأرسل الصورة هنا بدلاً من الملف."
            if lang == "ar"
            else
            "📄 <b>PDF detected.</b>\n\nPDF contents are not processed by OCR. Open the file, display the payment receipt clearly, take a screenshot, and send the image here instead.",
            parse_mode="HTML",
        )
        return
    await handle_receipt_upload(message, state)


@router.message(ReceiptStates.waiting_receipt)
async def reject_unsupported_receipt(message: Message):
    lang = await _lang(message.from_user.id)
    await message.answer(
        "❌ أرسل صورة واضحة للإيصال بصيغة JPG أو PNG أو WebP. إذا كان الإثبات PDF، افتحه والتقط Screenshot للصفحة التي تحتوي على الإيصال ثم أرسل الصورة."
        if lang == "ar"
        else
        "❌ Send a clear JPG, PNG, or WebP image of the receipt. If the proof is a PDF, open it, screenshot the page containing the receipt, and send the image instead."
    )
