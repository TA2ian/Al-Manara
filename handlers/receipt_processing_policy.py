"""Customer receipt-processing entrypoint.

The canonical receipt service owns processing and progress UX for both Telegram
photos and documents, preventing divergent behavior between upload types.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from services.receipt_service import handle_receipt_upload
from states import ReceiptStates

router = Router()


@router.message(ReceiptStates.waiting_receipt, F.photo)
async def process_receipt_photo(message: Message, state: FSMContext):
    await handle_receipt_upload(message, state)
