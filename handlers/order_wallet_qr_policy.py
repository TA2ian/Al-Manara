"""Order-context wallet QR safety guard.

The wallet registry supports an explicit QR-skip warning for standalone wallet
management, but an order cannot be created without a verified stored QR. When
wallet registration was started from an order, these callbacks therefore stay
inside the QR step instead of allowing the session to continue toward a quote.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from states import WalletStates

router = Router()


async def _block_order_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("return_to_order"):
        return False
    lang = data.get("language", "ar")
    await callback.answer(
        "❌ لا يمكن تخطي QR عند إنشاء طلب. أرسل QR المطابق لنفس العنوان." if lang == "ar" else
        "❌ QR cannot be skipped during order creation. Send the matching QR for this address.",
        show_alert=True,
    )
    return True


@router.callback_query(WalletStates.waiting_qr, F.data.in_({"wallet_qr_skip_prompt", "wallet_qr_skip_confirm"}))
async def block_order_wallet_qr_skip(callback: CallbackQuery, state: FSMContext):
    """Block QR skip when wallet registration is part of an active order."""
    if await _block_order_skip(callback, state):
        return
