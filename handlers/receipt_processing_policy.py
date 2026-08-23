"""Customer receipt-processing UX policy.

Displays a localized processing message while the canonical receipt upload
implementation performs OCR, verification, persistence, and admin notification.
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import get_pool
from states import ReceiptStates

logger = logging.getLogger(__name__)
router = Router()


async def _get_lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1",
            telegram_id,
        )
    return row["language"] if row and row["language"] in ("ar", "en") else "ar"


@router.message(ReceiptStates.waiting_receipt, F.photo)
async def process_receipt_with_progress(message: Message, state: FSMContext):
    """Display localized progress while the canonical receipt flow processes the image."""
    lang = await _get_lang(message.from_user.id)
    progress_text = (
        "⏳ <b>جارٍ معالجة صورة الإيصال...</b>\n\n"
        "🔍 يتم الآن قراءة بيانات التحويل والتحقق منها.\n"
        "يرجى الانتظار حتى تظهر نتيجة التحقق."
        if lang == "ar" else
        "⏳ <b>Processing your receipt...</b>\n\n"
        "🔍 We are reading the transfer details and verifying them.\n"
        "Please wait for the verification result."
    )
    failure_text = (
        "❌ <b>تعذر معالجة صورة الإيصال.</b>\n\n"
        "يرجى المحاولة مرة أخرى بصورة واضحة."
        if lang == "ar" else
        "❌ <b>We could not process the receipt image.</b>\n\n"
        "Please try again with a clear image."
    )

    progress = await message.answer(progress_text, parse_mode="HTML")
    try:
        from handlers.my_orders import handle_receipt_upload
        await handle_receipt_upload(message, state)
    except Exception:
        logger.exception("Receipt processing failed for order in customer flow")
        try:
            await progress.edit_text(failure_text, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to render receipt processing failure message")
        return

    try:
        await progress.delete()
    except Exception:
        logger.debug("Receipt processing progress message could not be deleted", exc_info=True)
