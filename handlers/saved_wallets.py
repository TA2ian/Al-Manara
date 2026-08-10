"""Saved wallet handlers that sit before the legacy order QR prompts.

This module keeps the existing order flow intact while making a saved wallet
carry its QR photo ID. A saved wallet with a stored QR never asks the customer
to upload the same QR again.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database import get_pool
from states import OrderStates
from keyboards.inline import currency_selection_keyboard
from services.locale_service import locale_service

router = Router()


async def _get_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1",
            telegram_id,
        )


@router.callback_query(F.data.startswith("order_use_saved_"))
async def use_saved_wallet(callback: CallbackQuery, state: FSMContext):
    """Select a saved wallet and reuse its stored QR when available."""
    try:
        address_id = int(callback.data.removeprefix("order_use_saved_"))
    except ValueError:
        await callback.answer("❌ Invalid wallet", show_alert=True)
        return

    user = await _get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ User not found", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        wallet = await conn.fetchrow(
            """
            SELECT id, address, network, label, qr_photo_id
            FROM saved_addresses
            WHERE id = $1 AND user_id = $2
            """,
            address_id,
            user["id"],
        )

    if not wallet:
        await callback.answer("❌ المحفظة غير موجودة", show_alert=True)
        return

    lang = user["language"] or "ar"
    await state.update_data(
        wallet_address=wallet["address"],
        network=wallet["network"],
        wallet_qr_photo_id=wallet["qr_photo_id"],
        address_from_saved=True,
        saved_address_id=wallet["id"],
    )

    label = wallet["label"] or ("محفظة محفوظة" if lang == "ar" else "Saved wallet")
    await callback.message.edit_text(
        (
            f"✅ <b>{label}</b>\n\n"
            f"📍 <code>{wallet['address']}</code>\n"
            f"🌐 {wallet['network']}\n"
            f"📸 رمز QR: {'محفوظ ✓' if wallet['qr_photo_id'] else 'غير محفوظ'}"
        )
        if lang == "ar"
        else (
            f"✅ <b>{label}</b>\n\n"
            f"📍 <code>{wallet['address']}</code>\n"
            f"🌐 {wallet['network']}\n"
            f"📸 QR: {'Saved ✓' if wallet['qr_photo_id'] else 'Not saved'}"
        ),
        parse_mode="HTML",
    )

    # A saved QR is already attached to the wallet; do not ask for it again.
    if wallet["qr_photo_id"]:
        await callback.message.answer(
            locale_service.get("select_currency", lang),
            reply_markup=currency_selection_keyboard(lang),
        )
        await state.set_state(OrderStates.waiting_currency)
    else:
        # Preserve the legacy first-time QR prompt for wallets created before
        # persistent QR support was added.
        qr_prompt = (
            "📸 <b>أرسل رمز QR لهذه المحفظة</b>\n\n"
            "سيتم حفظه مع العنوان لاستخدامه تلقائياً في الطلبات القادمة."
            if lang == "ar"
            else (
                "📸 <b>Send a QR code for this wallet</b>\n\n"
                "It will be saved with the address and reused automatically later."
            )
        )
        await callback.message.answer(
            qr_prompt,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="⏭️ تخطي" if lang == "ar" else "⏭️ Skip",
                    callback_data="skip_wallet_qr",
                )]
            ]),
            parse_mode="HTML",
        )
        await state.set_state(OrderStates.waiting_wallet_qr)

    await callback.answer()


@router.callback_query(OrderStates.waiting_save_address, F.data == "save_address_yes")
async def save_wallet_with_qr(callback: CallbackQuery, state: FSMContext):
    """Save the current wallet together with its QR photo ID, if supplied."""
    user = await _get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ User not found", show_alert=True)
        return

    data = await state.get_data()
    address = data.get("wallet_address", "").strip()
    network = data.get("network", "").strip()
    qr_photo_id = data.get("wallet_qr_photo_id")

    if not address or network not in {"TRC20", "BEP20"}:
        await callback.answer("❌ بيانات المحفظة غير صالحة", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id FROM saved_addresses
            WHERE user_id = $1 AND address = $2 AND network = $3
            ORDER BY id DESC LIMIT 1
            """,
            user["id"],
            address,
            network,
        )

        if existing:
            await conn.execute(
                """
                UPDATE saved_addresses
                SET qr_photo_id = COALESCE($1, qr_photo_id), updated_at = NOW()
                WHERE id = $2 AND user_id = $3
                """,
                qr_photo_id,
                existing["id"],
                user["id"],
            )
        else:
            await conn.execute(
                """
                INSERT INTO saved_addresses
                    (user_id, address, network, qr_photo_id, is_default)
                VALUES ($1, $2, $3, $4, FALSE)
                """,
                user["id"],
                address,
                network,
                qr_photo_id,
            )

    lang = user["language"] or "ar"
    await callback.message.edit_text(
        (
            "💾 <b>تم حفظ المحفظة بنجاح</b>\n\n"
            f"🌐 الشبكة: {network}\n"
            f"📸 QR: {'تم حفظه ✓' if qr_photo_id else 'لم يتم إرفاقه'}"
        )
        if lang == "ar"
        else (
            "💾 <b>Wallet saved successfully</b>\n\n"
            f"🌐 Network: {network}\n"
            f"📸 QR: {'Saved ✓' if qr_photo_id else 'Not provided'}"
        ),
        parse_mode="HTML",
    )
    await callback.message.answer(
        locale_service.get("select_currency", lang),
        reply_markup=currency_selection_keyboard(lang),
    )
    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()
