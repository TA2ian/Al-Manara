"""Saved wallet selection for order creation."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database import get_pool
from keyboards.inline import currency_selection_keyboard
from keyboards.wallet import SUPPORTED_WALLET_NETWORKS
from services.locale_service import locale_service
from states import OrderStates

router = Router()


async def _get_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT id, language FROM users WHERE telegram_id = $1", telegram_id)


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
    if not wallet or wallet["network"] not in SUPPORTED_WALLET_NETWORKS:
        await callback.answer(
            "❌ هذه المحفظة غير موثقة أو شبكتها غير مدعومة حالياً."
            if lang == "ar"
            else "❌ This wallet is not verified or its network is not currently supported.",
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
            f"✅ <b>{label}</b>\n\n📍 <code>{wallet['address']}</code>\n"
            f"🌐 {wallet['network']}\n📸 QR: محفوظ وموثق ✓\n\n"
            "🔒 لن يُطلب QR مرة أخرى لهذا العنوان."
        )
        if lang == "ar"
        else (
            f"✅ <b>{label}</b>\n\n📍 <code>{wallet['address']}</code>\n"
            f"🌐 {wallet['network']}\n📸 QR: Stored and verified ✓\n\n"
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
