"""Enforce the customer wallet registry as the only wallet source for orders.

A wallet QR is collected once during wallet registration, stored with the
verified wallet record, and reused for subsequent orders. The order flow must
never ask for the same QR again.
"""
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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order",
            callback_data="cancel_order"
        )]
    ])


def _wallet_choice_keyboard(rows, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for row in rows:
        label = row["label"] or ("بدون اسم" if lang == "ar" else "Unnamed")
        icon = "🔷" if row["network"] == "TRC20" else "🟡"
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {label} · {row['address'][:6]}...{row['address'][-4:]}",
                callback_data=f"order_use_saved_{row['id']}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="➕ إضافة محفظة جديدة" if lang == "ar" else "➕ Add a new wallet",
            callback_data="order_wallet_manual"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order",
            callback_data="cancel_order"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _continue_to_currency(message_or_callback, state: FSMContext, lang: str):
    """Resume an order after a verified wallet has been selected/registered."""
    await message_or_callback.answer(
        locale_service.get("select_currency", lang),
        reply_markup=currency_selection_keyboard(lang)
    )
    await state.set_state(OrderStates.waiting_currency)


@router.callback_query(F.data == "back_to_wallet")
async def back_to_wallet_selection(callback: CallbackQuery, state: FSMContext):
    """Return to verified-wallet selection without restarting address entry."""
    lang = await _lang(callback.from_user.id)
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
        await callback.message.edit_text(
            "👛 <b>اختر محفظة موثقة</b>\n\n"
            "اختر العنوان الذي تريد استخدامه لهذا الطلب. سيتم استخدام QR المحفوظ تلقائياً."
            if lang == "ar" else
            "👛 <b>Select a verified wallet</b>\n\n"
            "Choose the address for this order. Its stored QR will be reused automatically.",
            reply_markup=_wallet_choice_keyboard(rows, lang),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        "👛 <b>إضافة محفظة للاستلام</b>\n\n"
        "لا توجد محفظة موثقة بعد. أرسل الآن عنوان BEP20 أو TRC20.\n"
        "بعد التحقق من العنوان سنطلب صورة QR المطابقة مرة واحدة فقط.\n\n"
        "🔒 بعد الحفظ سيُستخدم QR تلقائياً في الطلبات القادمة."
        if lang == "ar" else
        "👛 <b>Add a receiving wallet</b>\n\n"
        "No verified wallet is available yet. Send a BEP20 or TRC20 address now.\n"
        "After the address is validated, we will request the matching QR once.\n\n"
        "🔒 After saving, the QR will be reused automatically for future orders.",
        reply_markup=_cancel_order_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("order_use_saved_"))
async def use_verified_saved_wallet(callback: CallbackQuery, state: FSMContext):
    """Select a previously verified wallet without asking for its QR again."""
    try:
        wallet_id = int(callback.data.replace("order_use_saved_", ""))
    except ValueError:
        await callback.answer("Invalid wallet", show_alert=True)
        return

    pool = await get_pool()
    lang = await _lang(callback.from_user.id)
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id)
        wallet = None
        if user:
            wallet = await conn.fetchrow(
                """SELECT id, address, network, qr_photo_id, label
                   FROM saved_addresses
                   WHERE id = $1 AND user_id = $2
                     AND deleted_at IS NULL
                     AND verification_status = 'verified'
                     AND qr_photo_id IS NOT NULL""",
                wallet_id, user["id"]
            )

    if not wallet:
        await callback.answer(
            "❌ هذه المحفظة غير موثقة أو لا تحتوي على QR محفوظ. أضف محفظة جديدة من محافظي."
            if lang == "ar" else
            "❌ This wallet is not verified or has no stored QR. Add a new wallet from My Wallets.",
            show_alert=True
        )
        return

    await state.update_data(
        wallet_address=wallet["address"],
        network=wallet["network"],
        wallet_qr_photo_id=wallet["qr_photo_id"],
        address_from_saved=True,
        wallet_id=wallet["id"],
    )

    await callback.message.edit_text(
        (
            "✅ <b>تم اختيار المحفظة الموثقة</b>\n\n"
            f"🏷️ {wallet['label'] or 'بدون اسم'}\n"
            f"🌐 {wallet['network']}\n"
            f"📍 <code>{wallet['address']}</code>\n\n"
            "🔒 QR محفوظ مسبقاً وسيُستخدم تلقائياً لهذا الطلب."
        ) if lang == "ar" else (
            "✅ <b>Verified wallet selected</b>\n\n"
            f"🏷️ {wallet['label'] or 'Unnamed'}\n"
            f"🌐 {wallet['network']}\n"
            f"📍 <code>{wallet['address']}</code>\n\n"
            "🔒 The stored QR will be reused automatically for this order."
        ),
        parse_mode="HTML"
    )
    await _continue_to_currency(callback.message, state, lang)
    await callback.answer()


@router.callback_query(F.data == "order_wallet_manual")
async def redirect_manual_wallet_to_registry(callback: CallbackQuery, state: FSMContext):
    """Register a new wallet once; never collect wallet/QR as per-order data."""
    lang = await _lang(callback.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        (
            "👛 <b>إضافة محفظة للاستلام</b>\n\n"
            "أرسل الآن عنوان BEP20 أو TRC20.\n"
            "بعد التحقق من العنوان سنطلب صورة QR المطابقة مرة واحدة فقط.\n\n"
            "🔒 بعد الحفظ سيُستخدم QR تلقائياً في هذا الطلب والطلبات القادمة."
        ) if lang == "ar" else (
            "👛 <b>Add a receiving wallet</b>\n\n"
            "Send a BEP20 or TRC20 address now.\n"
            "After the address is validated, we will request the matching QR once.\n\n"
            "🔒 After saving, the QR will be reused automatically for this and future orders."
        ),
        reply_markup=_cancel_order_keyboard(lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(OrderStates.waiting_wallet)
async def redirect_manual_wallet_message_to_registry(message: Message, state: FSMContext):
    """Redirect legacy order wallet input into the one-time wallet registry."""
    lang = await _lang(message.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await message.answer(
        (
            "👛 <b>تسجيل المحفظة مرة واحدة</b>\n\n"
            "أرسل عنوان BEP20 أو TRC20 الآن.\n"
            "سيتم التعرف على الشبكة والتحقق من العنوان تلقائياً، ثم سنطلب QR المطابق مرة واحدة.\n\n"
            "🔒 لن تحتاج إلى إرسال QR مرة أخرى لهذا العنوان."
        ) if lang == "ar" else (
            "👛 <b>One-time wallet registration</b>\n\n"
            "Send a BEP20 or TRC20 address now.\n"
            "The network and address will be validated automatically, then the matching QR will be requested once.\n\n"
            "🔒 You will not need to send the QR again for this address."
        ),
        reply_markup=_cancel_order_keyboard(lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "save_address_skip")
@router.callback_query(F.data == "skip_wallet_qr")
async def block_legacy_wallet_skip(callback: CallbackQuery, state: FSMContext):
    """Legacy safety net: per-order QR upload/skip is no longer supported."""
    lang = await _lang(callback.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        "❌ <b>لا يمكن تخطي التحقق.</b>\n\nأضف محفظة موثقة مرة واحدة: العنوان أولاً ثم QR المطابق. بعد الحفظ سيُستخدم QR تلقائياً."
        if lang == "ar" else
        "❌ <b>Verification cannot be skipped.</b>\n\nRegister a wallet once: address first, then the matching QR. After saving, the QR will be reused automatically.",
        reply_markup=_cancel_order_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(OrderStates.waiting_wallet_qr, F.photo)
async def block_legacy_wallet_qr_upload(message: Message, state: FSMContext):
    """Prevent stale FSM sessions from accepting a QR per order."""
    lang = await _lang(message.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await message.answer(
        "❌ هذا الطلب لا يستقبل QR منفصلاً. سجّل المحفظة مرة واحدة من خلال العنوان ثم QR المطابق؛ سيُحفظ ويُستخدم تلقائياً."
        if lang == "ar" else
        "❌ This order does not accept a separate QR. Register the wallet once with the address and matching QR; it will be stored and reused automatically.",
        reply_markup=_cancel_order_keyboard(lang),
    )


@router.message(OrderStates.waiting_wallet_qr)
async def block_legacy_wallet_qr_message(message: Message):
    """Prevent stale FSM sessions from falling through to legacy QR handlers."""
    lang = await _lang(message.from_user.id)
    await message.answer(
        "❌ لا يتم رفع QR مع كل طلب. اختر محفظة موثقة محفوظة أو أضف محفظة جديدة مرة واحدة."
        if lang == "ar" else
        "❌ QR is not uploaded with every order. Use a saved verified wallet or register a new wallet once."
    )
