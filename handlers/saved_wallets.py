"""Saved wallet selection for order creation.

Verified wallets are reusable only when their address and QR were both
verified and stored during one-time wallet registration. Per-order QR upload
or skipping QR is intentionally not supported.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database import get_pool
from states import OrderStates, WalletStates
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
    """Select a verified saved wallet and reuse its stored QR."""
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
            WHERE id = $1
              AND user_id = $2
              AND deleted_at IS NULL
              AND verification_status = 'verified'
              AND qr_photo_id IS NOT NULL
            """,
            address_id,
            user["id"],
        )

    lang = user["language"] or "ar"
    if not wallet:
        await callback.answer(
            "❌ هذه المحفظة غير موثقة أو لا تحتوي على QR محفوظ. استخدم محافظي لإضافة/توثيق محفظة جديدة."
            if lang == "ar" else
            "❌ This wallet is not verified or has no stored QR. Use My Wallets to register a new verified wallet.",
            show_alert=True,
        )
        return

    await state.update_data(
        wallet_address=wallet["address"],
        network=wallet["network"],
        wallet_qr_photo_id=wallet["qr_photo_id"],
        address_from_saved=True,
        saved_address_id=wallet["id"],
        wallet_id=wallet["id"],
    )

    label = wallet["label"] or ("محفظة محفوظة" if lang == "ar" else "Saved wallet")
    await callback.message.edit_text(
        (
            f"✅ <b>{label}</b>\n\n"
            f"📍 <code>{wallet['address']}</code>\n"
            f"🌐 {wallet['network']}\n"
            "📸 QR: محفوظ وموثق ✓\n\n"
            "🔒 لن يُطلب QR مرة أخرى لهذا العنوان."
        )
        if lang == "ar"
        else (
            f"✅ <b>{label}</b>\n\n"
            f"📍 <code>{wallet['address']}</code>\n"
            f"🌐 {wallet['network']}\n"
            "📸 QR: Stored and verified ✓\n\n"
            "🔒 The QR will not be requested again for this address."
        ),
        parse_mode="HTML",
    )
    await callback.message.answer(
        locale_service.get("select_currency", lang),
        reply_markup=currency_selection_keyboard(lang),
    )
    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()


@router.callback_query(OrderStates.waiting_save_address, F.data == "save_address_yes")
async def save_wallet_with_qr(callback: CallbackQuery, state: FSMContext):
    """Save a wallet only when its QR was supplied and verified."""
    user = await _get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ User not found", show_alert=True)
        return

    data = await state.get_data()
    address = (data.get("wallet_address") or "").strip()
    network = (data.get("network") or "").strip()
    qr_photo_id = data.get("wallet_qr_photo_id")

    if not address or network not in {"TRC20", "BEP20"} or not qr_photo_id:
        await callback.answer(
            "❌ لا يمكن حفظ المحفظة بدون QR مطابق وموثق." if (user["language"] or "ar") == "ar" else
            "❌ A wallet cannot be saved without a matching verified QR.",
            show_alert=True,
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id FROM saved_addresses
            WHERE user_id = $1 AND address = $2 AND network = $3 AND deleted_at IS NULL
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
                SET qr_photo_id = $1,
                    verification_status = 'verified',
                    verified_at = COALESCE(verified_at, NOW()),
                    updated_at = NOW()
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
                    (user_id, address, network, qr_photo_id, is_default, verification_status, verified_at)
                VALUES ($1, $2, $3, $4, FALSE, 'verified', NOW())
                """,
                user["id"],
                address,
                network,
                qr_photo_id,
            )

    lang = user["language"] or "ar"
    await callback.message.edit_text(
        (
            "💾 <b>تم حفظ المحفظة وتوثيق QR</b>\n\n"
            f"🌐 الشبكة: {network}\n"
            "📸 QR: محفوظ وموثق ✓\n\n"
            "🔒 سيُستخدم تلقائياً في الطلبات القادمة."
        )
        if lang == "ar"
        else (
            "💾 <b>Wallet and QR verified and saved</b>\n\n"
            f"🌐 Network: {network}\n"
            "📸 QR: Stored and verified ✓\n\n"
            "🔒 It will be reused automatically in future orders."
        ),
        parse_mode="HTML",
    )
    await callback.message.answer(
        locale_service.get("select_currency", lang),
        reply_markup=currency_selection_keyboard(lang),
    )
    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()
