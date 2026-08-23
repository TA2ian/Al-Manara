"""Legacy safety guard for stale per-order wallet QR FSM sessions.

Wallet registration now belongs to the verified wallet registry. This router
runs before the retired per-order QR flow so users who still have an old
``waiting_wallet_qr`` session are redirected to the canonical wallet registry.
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
        "👛 <b>تسجيل المحفظة</b>\n\n"
        "هذه جلسة قديمة كانت تطلب QR داخل الطلب، وقد تم إيقاف هذا المسار.\n\n"
        "يمكنك تسجيل محفظتك بالطريقة المناسبة لك:\n"
        "• إرسال عنوان المحفظة ثم QR المطابق.\n"
        "• أو إرسال QR فقط، وسيتم استخراج العنوان والتحقق منه تلقائياً.\n\n"
        "إذا أرسلت QR مع عنوان في وصف الصورة، فسيتم التحقق من تطابقهما أيضاً.\n\n"
        "بعد نجاح التحقق تُحفظ المحفظة وQR، ويُعاد استخدامهما تلقائياً في الطلبات القادمة."
        if lang == "ar" else
        "👛 <b>Wallet registration</b>\n\n"
        "This is a legacy session that requested a QR inside the order. That path has been retired.\n\n"
        "You can register your wallet in either supported way:\n"
        "• Send the wallet address first, then the matching QR.\n"
        "• Or send the QR only; the address will be extracted and verified automatically.\n\n"
        "If you send a QR with an address in its caption, the two inputs will also be checked for a match.\n\n"
        "After successful verification, the wallet and QR are saved and reused automatically for future orders."
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
