"""Safety guard for stale per-order wallet QR FSM sessions.

Wallet registration now belongs to the verified wallet registry. This router
runs before the legacy order router so users who already had an old
``waiting_wallet_qr`` session cannot upload or skip a QR inside an order.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from states import OrderStates, WalletStates
from database import get_pool

router = Router()


async def _lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1", telegram_id
        )
    return (row["language"] if row else "ar") or "ar"


def _wallet_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👛 إضافة محفظة موثقة" if lang == "ar" else "👛 Add verified wallet",
            callback_data="wallet_add",
        )],
        [InlineKeyboardButton(
            text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order",
            callback_data="cancel_order",
        )],
    ])


async def _redirect(target: Message | CallbackQuery, state: FSMContext, telegram_id: int) -> None:
    lang = await _lang(telegram_id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    text = (
        "👛 <b>تسجيل المحفظة مرة واحدة</b>\n\n"
        "هذه جلسة قديمة كانت تطلب QR داخل الطلب. تم إيقاف هذا المسار.\n\n"
        "أضف المحفظة مرة واحدة من خلال العنوان ثم QR المطابق. بعد التوثيق سيُحفظ QR ويُستخدم تلقائياً في الطلبات القادمة."
        if lang == "ar" else
        "👛 <b>One-time wallet registration</b>\n\n"
        "This is a legacy order session that requested a QR inside the order. That path is disabled.\n\n"
        "Register the wallet once with its address and matching QR. After verification, the stored QR is reused automatically for future orders."
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=_wallet_keyboard(lang), parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=_wallet_keyboard(lang), parse_mode="HTML")


@router.callback_query(OrderStates.waiting_wallet_qr)
async def block_legacy_wallet_qr_callbacks(callback: CallbackQuery, state: FSMContext):
    """Block callbacks from the retired per-order QR state."""
    await _redirect(callback, state, callback.from_user.id)


@router.message(OrderStates.waiting_wallet_qr)
async def block_legacy_wallet_qr_messages(message: Message, state: FSMContext):
    """Block messages/photos from the retired per-order QR state."""
    await _redirect(message, state, message.from_user.id)
