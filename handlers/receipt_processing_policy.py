"""Customer receipt-processing UX policy.

Shows an explicit processing message while the existing ShamCash OCR/verification
handler is working, then removes the temporary message after the real result is
sent. This keeps the verification logic in one place while making slow OCR work
visible to the customer.
"""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from states import ReceiptStates

logger = logging.getLogger(__name__)
router = Router()


@router.message(ReceiptStates.waiting_receipt, F.photo)
async def process_receipt_with_progress(message: Message, state: FSMContext):
    """Display progress while the existing receipt verifier processes the image."""
    progress = await message.answer(
        "⏳ <b>جارٍ معالجة صورة الإيصال...</b>\n\n"
        "🔍 يتم الآن قراءة بيانات التحويل والتحقق منها.\n"
        "يرجى الانتظار حتى تظهر نتيجة التحقق."
    , parse_mode="HTML")

    try:
        # Reuse the established verification implementation so there is only
        # one source of truth for OCR, attempts, status updates and admin alerts.
        from handlers.my_orders import handle_receipt_upload
        await handle_receipt_upload(message, state)
    except Exception:
        logger.exception("Receipt processing failed for order in customer flow")
        try:
            await progress.edit_text(
                "❌ <b>تعذر معالجة صورة الإيصال.</b>\n\n"
                "يرجى المحاولة مرة أخرى بصورة واضحة."
            , parse_mode="HTML")
            return
        except Exception:
            pass

    # The real handler sends the authoritative result. Remove the temporary
    # progress message so the conversation remains clean.
    try:
        await progress.delete()
    except Exception:
        pass
