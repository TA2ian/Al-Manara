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


def _wallet_registration_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👛 إضافة محفظة موثقة" if lang == "ar" else "👛 Add a verified wallet",
            callback_data="wallet_add"
        )],
        [InlineKeyboardButton(
            text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order",
            callback_data="cancel_order"
        )]
    ])


async def _continue_to_currency(message_or_callback, state: FSMContext, lang: str):
    """Resume an order after a verified wallet has been selected/registered."""
    await message_or_callback.answer(
        locale_service.get("select_currency", lang),
        reply_markup=currency_selection_keyboard(lang)
    )
    await state.set_state(OrderStates.waiting_currency)


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
    """Do not collect wallet/QR inside an order; register it once in My Wallets."""
    lang = await _lang(callback.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        (
            "👛 <b>إضافة محفظة للاستلام</b>\n\n"
            "سيتم تسجيل المحفظة مرة واحدة فقط.\n"
            "أرسل عنوان BEP20 أو TRC20، ثم أرسل QR المطابق له.\n\n"
            "🔒 بعد التوثيق سيتم حفظ QR مع المحفظة واستخدامه تلقائياً في الطلبات القادمة؛ لن تحتاج لإرساله مرة أخرى."
        ) if lang == "ar" else (
            "👛 <b>Add a receiving wallet</b>\n\n"
            "The wallet will be registered once.\n"
            "Send a BEP20 or TRC20 address, then send the matching QR.\n\n"
            "🔒 After verification, the stored QR is reused automatically in future orders."
        ),
        reply_markup=_wallet_registration_keyboard(lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(OrderStates.waiting_wallet)
async def redirect_manual_wallet_message_to_registry(message: Message, state: FSMContext):
    """Legacy order wallet input is redirected to the one-time wallet registry."""
    lang = await _lang(message.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await message.answer(
        (
            "👛 <b>تسجيل المحفظة مرة واحدة</b>\n\n"
            "لا نطلب QR في كل طلب. سيتم حفظه مع المحفظة بعد مطابقته أول مرة.\n\n"
            "أرسل الآن عنوان BEP20 أو TRC20، ثم QR المطابق."
        ) if lang == "ar" else (
            "👛 <b>One-time wallet registration</b>\n\n"
            "We do not ask for the QR on every order. It will be stored with the wallet after the first successful match.\n\n"
            "Send a BEP20 or TRC20 address, then the matching QR."
        ),
        reply_markup=_wallet_registration_keyboard(lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "save_address_skip")
async def block_legacy_wallet_skip(callback: CallbackQuery, state: FSMContext):
    """Legacy safety net: a wallet cannot be saved without its QR."""
    lang = await _lang(callback.from_user.id)
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        "❌ لا يمكن تخطي QR. أضف المحفظة من محافظي مع QR مطابق وسيتم حفظه للطلبات القادمة."
        if lang == "ar" else
        "❌ QR cannot be skipped. Add the wallet from My Wallets with a matching QR; it will be stored for future orders.",
        reply_markup=_wallet_registration_keyboard(lang),
    )
    await callback.answer()
