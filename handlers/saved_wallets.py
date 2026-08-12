"""Persistence helpers for wallet data collected during the order flow.

Wallet selection itself is owned by ``order_wallet_policy``. This module only
handles the post-registration save action, avoiding duplicate order callbacks
that could bypass the verified-wallet policy.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database import get_pool
from states import OrderStates
from services.locale_service import locale_service

router = Router()


async def _get_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1",
            telegram_id,
        )


@router.callback_query(OrderStates.waiting_save_address, F.data == "save_address_yes")
async def save_wallet_with_qr(callback: CallbackQuery, state: FSMContext):
    """Save the current wallet together with its verified QR photo ID."""
    user = await _get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ User not found", show_alert=True)
        return

    data = await state.get_data()
    address = data.get("wallet_address", "").strip()
    network = data.get("network", "").strip()
    qr_photo_id = data.get("wallet_qr_photo_id")

    # New policy: a wallet cannot become a reusable saved wallet without a
    # matching QR. The registry is the authoritative source for verification.
    if not address or network not in {"TRC20", "BEP20"} or not qr_photo_id:
        lang = user["language"] or "ar"
        await callback.answer(
            "❌ يجب توثيق المحفظة عبر العنوان وQR المطابق من محافظي."
            if lang == "ar" else
            "❌ The wallet must be verified with its address and matching QR from My Wallets.",
            show_alert=True,
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id FROM saved_addresses
            WHERE user_id = $1 AND address = $2 AND network = $3
              AND deleted_at IS NULL
            ORDER BY id DESC LIMIT 1
            """,
            user["id"],
            address,
            network,
        )

        if existing:
            # Do not downgrade or overwrite verification state here. The
            # dedicated wallet registry owns verified wallet records.
            await callback.answer(
                "❌ المحفظة موجودة بالفعل. استخدم المحفظة الموثقة من محافظي."
                if (user["language"] or "ar") == "ar" else
                "❌ This wallet already exists. Use the verified wallet from My Wallets.",
                show_alert=True,
            )
            return

        await conn.execute(
            """
            INSERT INTO saved_addresses
                (user_id, address, network, qr_photo_id, is_default,
                 verification_status, verified_at)
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
            "💾 <b>تم حفظ المحفظة بنجاح</b>\n\n"
            f"🌐 الشبكة: {network}\n"
            "📸 QR: تم حفظه ✓"
        )
        if lang == "ar"
        else (
            "💾 <b>Wallet saved successfully</b>\n\n"
            f"🌐 Network: {network}\n"
            "📸 QR: Saved ✓"
        ),
        parse_mode="HTML",
    )

    # Resume at currency selection. The stored wallet/QR remain in FSM data.
    await callback.message.answer(
        locale_service.get("select_currency", lang),
        reply_markup=__import__("keyboards.inline", fromlist=["currency_selection_keyboard"]).currency_selection_keyboard(lang),
    )
    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()
