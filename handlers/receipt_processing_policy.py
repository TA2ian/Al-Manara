"""Customer receipt-processing UX policy.

Shows an explicit processing message while the existing ShamCash OCR/verification
handler is working, then removes the temporary message after the real result is
sent. This keeps the verification logic in one place while making slow OCR work
visible to the customer without exposing technical errors.
"""
import logging

from aiogram import Router, F
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
    return (row["language"] if row and row["language"] in ("ar", "en") else "ar")


@router.message(ReceiptStates.waiting_receipt, F.photo)
async def process_receipt_with_progress(message: Message, state: FSMContext):
    """Display localized progress while the existing receipt verifier processes the image."""
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
        # Reuse the established verification implementation so there is only
        # one source of truth for OCR, attempts, status updates and admin alerts.
        from handlers.my_orders import handle_receipt_upload
        await handle_receipt_upload(message, state)
    except Exception:
        logger.exception("Receipt processing failed for order in customer flow")
        try:
            await progress.edit_text(failure_text, parse_mode="HTML")
            return
        except Exception:
            pass

    # The real handler sends the authoritative result. Remove the temporary
    # progress message so the conversation remains clean.
    try:
        await progress.delete()
    except Exception:
        pass
