"""Safety guard for stale per-order wallet QR FSM sessions."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database import get_pool
from keyboards.wallet import wallet_network_keyboard
from states import OrderStates, WalletStates

router = Router()


async def _lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


def _wallet_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👛 إضافة محفظة موثقة" if lang == "ar" else "👛 Add verified wallet", callback_data="wallet_add")
    ], [
        InlineKeyboardButton(text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order", callback_data="cancel_order")
    ]])


async def _redirect(target: Message | CallbackQuery, state: FSMContext, telegram_id: int) -> None:
    lang = await _lang(telegram_id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_network)
    text = (
        "👛 <b>تسجيل المحفظة</b>\n\n"
        "تم إيقاف جلسة المحفظة القديمة. سنكمل الآن عبر مسار تسجيل المحفظة الموحد.\n\n"
        "اختر شبكة USDT أولاً، ثم أرسل العنوان أو QR أو شارك المحفظة مباشرة من تطبيق محفظتك.\n\n"
        "🔐 سيتم التحقق من العنوان وفق الشبكة المختارة ومطابقته مع QR قبل اعتماده."
        if lang == "ar" else
        "👛 <b>Wallet registration</b>\n\n"
        "The old wallet session has been retired. We will continue through the unified wallet registration flow.\n\n"
        "Select the USDT network first, then send the address, QR, or share the wallet directly from your wallet app.\n\n"
        "🔐 The address will be validated for the selected network and matched with the QR before acceptance."
    )
    markup = wallet_network_keyboard(lang, cancel_callback="cancel_order")
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(OrderStates.waiting_wallet_qr)
async def block_legacy_wallet_qr_callbacks(callback: CallbackQuery, state: FSMContext):
    await _redirect(callback, state, callback.from_user.id)


@router.message(OrderStates.waiting_wallet_qr)
async def block_legacy_wallet_qr_messages(message: Message, state: FSMContext):
    await _redirect(message, state, message.from_user.id)
