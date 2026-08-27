"""Enforce the customer wallet registry as the only wallet source for orders."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database import get_pool
from keyboards.inline import currency_selection_keyboard
from keyboards.wallet import SUPPORTED_WALLET_NETWORKS, wallet_network_keyboard
from services.locale_service import locale_service
from states import OrderStates, WalletStates

router = Router()


async def _lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


def _cancel_order_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order", callback_data="cancel_order")
    ]])


async def _continue_to_currency(message_or_callback, state: FSMContext, lang: str):
    await message_or_callback.answer(locale_service.get("select_currency", lang), reply_markup=currency_selection_keyboard(lang))
    await state.set_state(OrderStates.waiting_currency)


async def _start_wallet_registration(target: Message | CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_network)
    text = (
        "👛 <b>إضافة محفظة للاستلام</b>\n\n"
        "اختر شبكة USDT أولاً، ثم أرسل العنوان أو صورة QR أو شارك المحفظة مباشرة من تطبيق محفظتك.\n\n"
        "🔐 سيتحقق البوت من العنوان وفق الشبكة المختارة ويطابقه مع QR قبل اعتماد المحفظة."
        if lang == "ar" else
        "👛 <b>Add a receiving wallet</b>\n\n"
        "Select the USDT network first, then send the address, QR image, or share the wallet directly from your wallet app.\n\n"
        "🔐 The bot validates the address for the selected network and matches it with the QR before accepting it."
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=wallet_network_keyboard(lang, cancel_callback="cancel_order"), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=wallet_network_keyboard(lang, cancel_callback="cancel_order"), parse_mode="HTML")


@router.callback_query(F.data == "back_to_wallet")
async def back_to_wallet_selection(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    lang = await _lang(callback.from_user.id)
    draft = await state.get_data()
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id)
        rows = []
        if user:
            rows = await conn.fetch(
                """SELECT id, address, network, label
                   FROM saved_addresses
                   WHERE user_id = $1 AND deleted_at IS NULL
                     AND verification_status = 'verified' AND qr_photo_id IS NOT NULL
                   ORDER BY is_default DESC, created_at DESC""",
                user["id"],
            )
    if rows:
        if draft.get("amount_usdt") is not None:
            await state.update_data(amount_usdt=draft["amount_usdt"], order_amount_usdt=draft.get("order_amount_usdt", draft["amount_usdt"]))
        buttons = []
        icons = {"BEP20": "🟡", "TRC20": "🔷", "TON": "💎", "ARB": "🔵", "SOLANA": "🟣", "ETH": "⚪"}
        for row in rows:
            label = row["label"] or ("بدون اسم" if lang == "ar" else "Unnamed")
            buttons.append([InlineKeyboardButton(text=f"{icons.get(row['network'], '🌐')} {label} · {row['address'][:6]}...{row['address'][-4:]}", callback_data=f"order_use_saved_{row['id']}")])
        buttons.append([InlineKeyboardButton(text="➕ إضافة محفظة جديدة" if lang == "ar" else "➕ Add a new wallet", callback_data="order_wallet_manual")])
        buttons.append([InlineKeyboardButton(text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order", callback_data="cancel_order")])
        await state.set_state(OrderStates.waiting_wallet)
        await callback.message.edit_text("👛 <b>اختر محفظة موثقة</b>\n\nاختر العنوان الذي تريد استخدامه لهذا الطلب." if lang == "ar" else "👛 <b>Select a verified wallet</b>\n\nChoose the wallet for this order.", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        return
    await _start_wallet_registration(callback, state, lang)


@router.callback_query(OrderStates.waiting_wallet, F.data.startswith("currency_"))
async def reject_currency_before_wallet(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.answer("👛 اختر المحفظة أولاً لمتابعة الطلب." if lang == "ar" else "👛 Select a wallet first to continue.", show_alert=True)


@router.callback_query(F.data == "order_wallet_manual")
async def open_wallet_registry_from_order(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await _start_wallet_registration(callback, state, lang)
    await callback.answer()


@router.message(OrderStates.waiting_wallet)
async def open_wallet_registry_from_message(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await _start_wallet_registration(message, state, lang)
