"""Authoritative ShamCash verification QR policy.

This router runs before the legacy verification QR handler. It verifies that
the QR encodes the same ShamCash receiving identifier entered by the customer,
then delegates successful submissions to the existing verification flow.
"""
import io
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from PIL import Image
from pyzbar.pyzbar import decode as qr_decode

from services.shamcash_qr_validator import qr_matches_account
from states import VerificationStates

logger = logging.getLogger(__name__)
router = Router()


async def _lang(telegram_id: int) -> str:
    from database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id=$1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


@router.message(VerificationStates.waiting_shamcash_qr, F.photo)
async def validate_shamcash_qr(message: Message, state: FSMContext):
    """Decode and match the ShamCash QR before submitting verification."""
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    account = (data.get("shamcash_account") or "").strip()
    if not account:
        await message.answer(
            "❌ بيانات ShamCash غير مكتملة. أعد التوثيق من البداية."
            if lang == "ar" else
            "❌ The ShamCash verification data is incomplete. Please restart verification."
        )
        await state.clear()
        return

    raw = io.BytesIO()
    try:
        await message.bot.download(file=message.photo[-1].file_id, destination=raw)
        raw.seek(0)
        decoded = qr_decode(Image.open(raw))
        qr_text = decoded[0].data.decode("utf-8", errors="replace").strip() if decoded else ""
    except Exception:
        logger.exception("Failed to decode ShamCash QR for user %s", message.from_user.id)
        qr_text = ""

    if not qr_text:
        await message.answer(
            "❌ لم أتمكن من قراءة QR لحساب ShamCash. أرسل صورة أوضح لنفس عنوان الاستلام."
            if lang == "ar" else
            "❌ I could not read the ShamCash QR. Please send a clearer QR image for the same receiving address."
        )
        return

    if not qr_matches_account(account, qr_text):
        await message.answer(
            "❌ <b>QR لا يطابق عنوان ShamCash المدخل.</b>\n\n"
            "أرسل QR المرتبط بنفس عنوان الاستلام الذي أدخلته. لم يتم إرسال طلب التوثيق إلى المشرف."
            if lang == "ar" else
            "❌ <b>The QR does not match the entered ShamCash address.</b>\n\n"
            "Send the QR linked to the same receiving address. The verification request was not submitted to the admin.",
            parse_mode="HTML",
        )
        return

    await state.update_data(shamcash_qr_photo_id=message.photo[-1].file_id)

    # Reuse the existing verification submission flow; do not duplicate it here.
    from handlers.verification import submit_verification
    await submit_verification(message, state)
