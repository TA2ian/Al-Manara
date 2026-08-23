"""Allow wallet registration to start from a QR image.

The customer may register a receiving wallet in either order:
1. address first, then matching QR; or
2. QR first, with the address extracted from the QR.

If Telegram provides a caption with the QR image, it is treated as an
independent address input and must match the decoded QR address.
"""
import io
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from PIL import Image

from services.media_security import validate_image_payload
from services.wallet_validator import WalletValidator
from states import WalletStates

logger = logging.getLogger(__name__)
router = Router()


def _normalize_qr_value(value: str) -> str:
    normalized = (value or "").strip()
    for prefix in ("ethereum:", "tron:", "trc20:", "bep20:", "usdt:"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    return normalized


def _caption_address(caption: str) -> str:
    """Accept a plain address caption; ignore ordinary descriptive captions."""
    candidate = _normalize_qr_value(caption)
    if not candidate:
        return ""
    network = WalletValidator.detect_network(candidate)
    if not network:
        return ""
    return candidate


async def _lang(telegram_id: int) -> str:
    from database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


@router.message(WalletStates.waiting_address, F.photo)
async def wallet_qr_first(message: Message, state: FSMContext):
    """Decode a QR-first wallet registration and continue to label entry."""
    lang = await _lang(message.from_user.id)
    raw = io.BytesIO()

    try:
        await message.bot.download(file=message.photo[-1].file_id, destination=raw)
        payload = raw.getvalue()
        validate_image_payload(payload, file_name="telegram-photo")
    except ValueError:
        await message.answer(
            "❌ صورة QR غير صالحة أو غير آمنة. أرسل صورة QR واضحة بصيغة مدعومة."
            if lang == "ar" else
            "❌ The QR image is invalid or unsafe. Send a clear QR image in a supported format."
        )
        return
    except Exception:
        logger.exception("Failed to download or validate wallet QR")
        await message.answer(
            "❌ تعذر معالجة صورة QR. أعد إرسالها من فضلك."
            if lang == "ar" else
            "❌ The QR image could not be processed. Please send it again."
        )
        return

    try:
        from pyzbar.pyzbar import decode as qr_decode
        decoded = qr_decode(Image.open(io.BytesIO(payload)))
        qr_text = decoded[0].data.decode("utf-8", errors="strict").strip() if decoded else ""
    except Exception:
        logger.exception("Failed to decode wallet QR")
        qr_text = ""

    qr_address = _normalize_qr_value(qr_text)
    network = WalletValidator.detect_network(qr_address)
    validation = WalletValidator.validate(qr_address, network) if network else {"valid": False}
    if not validation.get("valid"):
        await message.answer(
            "❌ لم أتمكن من التحقق من عنوان محفظة صالح داخل QR. أرسل QR أوضح، أو أرسل عنوان المحفظة كنص أولاً."
            if lang == "ar" else
            "❌ I could not verify a valid wallet address in this QR. Send a clearer QR, or send the wallet address as text first."
        )
        return

    caption_address = _caption_address(message.caption or "")
    if message.caption and not caption_address:
        await message.answer(
            "❌ النص المرفق بالصورة لا يبدو عنوان BEP20 أو TRC20 صالحًا. احذف النص وأرسل QR فقط، أو أرسل العنوان الصحيح مع الصورة."
            if lang == "ar" else
            "❌ The text attached to the image is not a valid BEP20/TRC20 address. Remove it and send the QR only, or send the correct address with the image."
        )
        return

    if caption_address and caption_address.lower() != qr_address.lower():
        await message.answer(
            "❌ العنوان المرفق مع صورة QR لا يطابق العنوان المستخرج من QR. أرسل الصورة والعنوان الصحيحين معًا."
            if lang == "ar" else
            "❌ The address attached to the QR image does not match the address encoded in the QR. Send the matching image and address together."
        )
        return

    await state.update_data(
        wallet_address=qr_address,
        network=network,
        wallet_qr_photo_id=message.photo[-1].file_id,
        wallet_qr_first=True,
    )
    await state.set_state(WalletStates.waiting_label)
    await message.answer(
        "✅ <b>تم التحقق من المحفظة عبر QR</b>\n\n"
        f"🌐 الشبكة: <b>{network}</b>\n"
        f"📍 العنوان: <code>{qr_address}</code>\n\n"
        "يمكنك الآن إرسال اسم لهذه المحفظة لحفظها."
        if lang == "ar" else
        "✅ <b>Wallet verified from QR</b>\n\n"
        f"🌐 Network: <b>{network}</b>\n"
        f"📍 Address: <code>{qr_address}</code>\n\n"
        "Now send a label to save this wallet.",
        parse_mode="HTML",
    )
