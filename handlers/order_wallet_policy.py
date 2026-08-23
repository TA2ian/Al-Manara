"""Enforce the customer wallet registry as the only wallet source for orders."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database import get_pool
from keyboards.inline import currency_selection_keyboard
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


def _wallet_choice_keyboard(rows, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for row in rows:
        label = row["label"] or ("بدون اسم" if lang == "ar" else "Unnamed")
        icon = "🔷" if row["network"] == "TRC20" else "🟡"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {label} · {row['address'][:6]}...{row['address'][-4:]}",
            callback_data=f"order_use_saved_{row['id']}",
        )])
    buttons.append([InlineKeyboardButton(
        text="➕ إضافة محفظة جديدة" if lang == "ar" else "➕ Add a new wallet",
        callback_data="order_wallet_manual",
    )])
    buttons.append([InlineKeyboardButton(
        text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order",
        callback_data="cancel_order",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _continue_to_currency(message_or_callback, state: FSMContext, lang: str):
    """Resume an order after a verified wallet has been selected/registered."""
    await message_or_callback.answer(
        locale_service.get("select_currency", lang),
        reply_markup=currency_selection_keyboard(lang),
    )
    await state.set_state(OrderStates.waiting_currency)


@router.callback_query(F.data == "back_to_wallet")
async def back_to_wallet_selection(callback: CallbackQuery, state: FSMContext):
    """Return to verified-wallet selection without restarting address entry."""
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
                   WHERE user_id = $1
                     AND deleted_at IS NULL
                     AND verification_status = 'verified'
                     AND qr_photo_id IS NOT NULL
                   ORDER BY is_default DESC, created_at DESC""",
                user["id"],
            )

    if rows:
        preserved = {}
        if draft.get("amount_usdt") is not None:
            preserved["amount_usdt"] = draft["amount_usdt"]
        if draft.get("order_amount_usdt") is not None:
            preserved["order_amount_usdt"] = draft["order_amount_usdt"]
        if preserved:
            await state.update_data(**preserved)

        await state.set_state(OrderStates.waiting_wallet)
        await callback.message.edit_text(
            "👛 <b>اختر محفظة موثقة</b>\n\nاختر العنوان الذي تريد استخدامه لهذا الطلب. سيتم استخدام QR المحفوظ تلقائياً."
            if lang == "ar" else
            "👛 <b>Select a verified wallet</b>\n\nChoose the address for this order. Its stored QR will be reused automatically.",
            reply_markup=_wallet_choice_keyboard(rows, lang),
            parse_mode="HTML",
        )
        return

    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        "👛 <b>إضافة محفظة للاستلام</b>\n\nلا توجد محفظة موثقة بعد. أرسل الآن عنوان BEP20 أو TRC20.\n"
        "بعد التحقق من العنوان سنطلب صورة QR المطابقة مرة واحدة فقط.\n\n🔒 بعد الحفظ سيُستخدم QR تلقائياً في الطلبات القادمة."
        if lang == "ar" else
        "👛 <b>Add a receiving wallet</b>\n\nNo verified wallet is available yet. Send a BEP20 or TRC20 address now.\n"
        "After the address is validated, we will request the matching QR once.\n\n🔒 After saving, the QR will be reused automatically for future orders.",
        reply_markup=_cancel_order_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(OrderStates.waiting_wallet, F.data.startswith("currency_"))
async def reject_currency_before_wallet(callback: CallbackQuery, state: FSMContext):
    """Do not allow a stale currency keyboard to bypass wallet selection."""
    lang = await _lang(callback.from_user.id)
    await callback.answer(
        "👛 اختر المحفظة أولاً لمتابعة الطلب." if lang == "ar" else
        "👛 Select a wallet first to continue.",
        show_alert=True,
    )


@router.callback_query(F.data == "order_wallet_manual")
async def open_wallet_registry_from_order(callback: CallbackQuery, state: FSMContext):
    """Start the canonical wallet registry for a new order wallet."""
    lang = await _lang(callback.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        (
            "👛 <b>إضافة محفظة للاستلام</b>\n\nأرسل الآن عنوان BEP20 أو TRC20.\n"
            "بعد التحقق من العنوان سنطلب صورة QR المطابقة مرة واحدة فقط.\n\n🔒 بعد الحفظ سيُستخدم QR تلقائياً في هذا الطلب والطلبات القادمة."
        ) if lang == "ar" else (
            "👛 <b>Add a receiving wallet</b>\n\nSend a BEP20 or TRC20 address now.\n"
            "After the address is validated, we will request the matching QR once.\n\n🔒 After saving, the QR will be reused automatically for this and future orders."
        ),
        reply_markup=_cancel_order_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(OrderStates.waiting_wallet)
async def open_wallet_registry_from_message(message: Message, state: FSMContext):
    """Start wallet registration when the customer types while choosing a wallet."""
    lang = await _lang(message.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await message.answer(
        (
            "👛 <b>تسجيل المحفظة مرة واحدة</b>\n\nأرسل عنوان BEP20 أو TRC20 الآن.\n"
            "سيتم التعرف على الشبكة والتحقق من العنوان تلقائياً، ثم سنطلب QR المطابق مرة واحدة.\n\n🔒 لن تحتاج إلى إرسال QR مرة أخرى لهذا العنوان."
        ) if lang == "ar" else (
            "👛 <b>One-time wallet registration</b>\n\nSend a BEP20 or TRC20 address now.\n"
            "The network and address will be validated automatically, then the matching QR will be requested once.\n\n🔒 You will not need to send the QR again for this address."
        ),
        reply_markup=_cancel_order_keyboard(lang),
    )
