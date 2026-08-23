"""Customer receipt upload entrypoint for document submissions."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import get_pool
from services.receipt_service import MAX_RECEIPT_ATTEMPTS, handle_receipt_upload
from states import ReceiptStates

router = Router()


async def _lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1",
            telegram_id,
        )
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
        await callback.answer(
            "الطلب غير موجود" if lang == "ar" else "Order not found",
            show_alert=True,
        )
        return
    if order["status"] != "waiting_payment":
        await callback.answer(
            "لا يمكن رفع إثبات لهذا الطلب حالياً"
            if lang == "ar"
            else "This order is not awaiting payment proof",
            show_alert=True,
        )
        return
    if int(order["receipt_upload_count"] or 0) >= MAX_RECEIPT_ATTEMPTS:
        await callback.answer(
            "❌ استنفدت محاولات رفع الإثبات"
            if lang == "ar"
            else "❌ Receipt attempts exhausted",
            show_alert=True,
        )
        return

    await state.update_data(receipt_order_id=order_id)
    prompt = (
        f"📎 <b>إرسال إثبات الدفع — الطلب #{order['order_number']}</b>\n\n"
        "أرسل صورة JPG/PNG/WebP أو ملف PDF مُصدّراً من ShamCash. سيتم التحقق من نوع الملف وقراءته آلياً عبر OCR قبل إرساله للمراجعة.\n\n"
        "⚠️ الحد الأقصى 12 MB، وPDF يجب ألا يتجاوز 3 صفحات."
        if lang == "ar"
        else
        f"📎 <b>Payment proof — order #{order['order_number']}</b>\n\n"
        "Send a JPG/PNG/WebP image or a PDF exported from ShamCash. The file type will be validated and its contents checked with OCR before review.\n\n"
        "⚠️ Maximum 12 MB; PDFs may contain up to 3 pages."
    )
    await callback.message.answer(prompt, parse_mode="HTML")
    await state.set_state(ReceiptStates.waiting_receipt)
    await callback.answer()


@router.message(ReceiptStates.waiting_receipt, F.document)
async def handle_receipt_document(message: Message, state: FSMContext):
    await handle_receipt_upload(message, state)


@router.message(ReceiptStates.waiting_receipt)
async def reject_unsupported_receipt(message: Message):
    lang = await _lang(message.from_user.id)
    await message.answer(
        "❌ صيغة الإثبات غير مدعومة. أرسل JPG أو PNG أو WebP أو PDF صالحاً من ShamCash."
        if lang == "ar"
        else
        "❌ Unsupported proof format. Send a valid ShamCash JPG, PNG, WebP, or PDF."
    )
