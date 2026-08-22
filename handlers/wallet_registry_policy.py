"""Authoritative wallet-registry policy for order-linked wallet registration.

Runs before the legacy wallet handlers. It preserves the amount selected before
wallet registration and supports QR images sent as Telegram photos or image
documents, using the shared robust QR decoder.
"""
import io

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import get_pool
from services.qr_decoder import decode_qr_bytes
from states import WalletStates

router = Router()


async def _user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id=$1", telegram_id
        )


def _normalize_wallet_qr(value: str) -> str:
    normalized = (value or "").strip()
    for prefix in ("ethereum:", "tron:", "trc20:", "bep20:", "usdt:"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    return normalized


async def _lang(telegram_id: int) -> str:
    user = await _user(telegram_id)
    return (user["language"] if user else "ar") or "ar"


async def _download_qr(message: Message, file_id: str) -> str:
    raw = io.BytesIO()
    await message.bot.download(file=file_id, destination=raw)
    return decode_qr_bytes(raw.getvalue())


async def _accept_qr(message: Message, state: FSMContext, file_id: str):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    address = (data.get("wallet_address") or "").strip()
    if not address:
        await message.answer(
            "❌ جلسة المحفظة غير مكتملة. أعد إضافة المحفظة من البداية."
            if lang == "ar" else
            "❌ The wallet session is incomplete. Please restart wallet registration."
        )
        await state.clear()
        return

    try:
        qr_text = await _download_qr(message, file_id)
    except Exception:
        qr_text = ""

    if not qr_text:
        await message.answer(
            "❌ لم أتمكن من قراءة QR. أرسل صورة QR واضحة، ويمكنك إرسالها كصورة أو كملف صورة."
            if lang == "ar" else
            "❌ I could not read the QR. Send a clear QR image, either as a photo or an image file."
        )
        return

    normalized = _normalize_wallet_qr(qr_text)
    if normalized.casefold() != address.casefold():
        await message.answer(
            "❌ QR لا يطابق العنوان المدخل. أرسل QR المطابق لنفس العنوان."
            if lang == "ar" else
            "❌ The QR does not match the entered address. Send the QR for the same address."
        )
        return

    await state.update_data(wallet_qr_photo_id=file_id)
    await state.set_state(WalletStates.waiting_label)
    await message.answer(
        "🏷️ أرسل اسماً لهذا العنوان، مثل: Binance أو محفظتي الرئيسية."
        if lang == "ar" else
        "🏷️ Send a label for this address, e.g. Binance or Main Wallet."
    )


@router.message(WalletStates.waiting_qr, F.photo)
async def wallet_qr_photo(message: Message, state: FSMContext):
    await _accept_qr(message, state, message.photo[-1].file_id)


@router.message(WalletStates.waiting_qr, F.document)
async def wallet_qr_document(message: Message, state: FSMContext):
    """Accept QR screenshots/images sent as Telegram documents."""
    document = message.document
    mime = (document.mime_type or "").lower()
    if not mime.startswith("image/"):
        lang = await _lang(message.from_user.id)
        await message.answer(
            "❌ أرسل صورة QR فقط، وليس ملفاً من نوع آخر."
            if lang == "ar" else
            "❌ Please send the QR as an image, not another file type."
        )
        return
    await _accept_qr(message, state, document.file_id)


@router.message(WalletStates.waiting_label, F.text)
async def wallet_label_preserve_order_state(message: Message, state: FSMContext):
    """Save the verified wallet without losing amount_usdt from the order FSM."""
    user = await _user(message.from_user.id)
    if not user:
        await message.answer("❌ User not found")
        return
    lang = user["language"] or "ar"
    label = (message.text or "").strip()[:64]
    if not label:
        await message.answer("❌ الاسم مطلوب." if lang == "ar" else "❌ A label is required.")
        return

    data = await state.get_data()
    address = data.get("wallet_address")
    network = data.get("network")
    qr_photo_id = data.get("wallet_qr_photo_id")
    if not address or not network or not qr_photo_id:
        await message.answer(
            "❌ بيانات المحفظة غير مكتملة. أعد إضافة المحفظة من البداية."
            if lang == "ar" else
            "❌ Wallet registration data is incomplete. Please restart wallet registration."
        )
        await state.clear()
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM saved_addresses WHERE user_id=$1 AND address=$2 AND network=$3 AND deleted_at IS NULL",
            user["id"], address, network,
        )
        if existing:
            await message.answer(
                "❌ هذا العنوان موجود بالفعل. لا يمكن تعديله؛ احذف العنوان الحالي ثم أضفه من جديد."
                if lang == "ar" else
                "❌ This address already exists. Delete it first and add it again."
            )
            return
        row = await conn.fetchrow(
            """INSERT INTO saved_addresses
               (user_id,address,network,label,qr_photo_id,is_default,verification_status,verified_at)
               VALUES ($1,$2,$3,$4,$5,FALSE,'verified',NOW())
               RETURNING id,address,network,qr_photo_id""",
            user["id"], address, network, label, qr_photo_id,
        )

    preserved = {
        "amount_usdt": data.get("amount_usdt"),
        "return_to_order": bool(data.get("return_to_order")),
    }
    await state.clear()

    if preserved["return_to_order"]:
        update = {
            "wallet_address": row["address"],
            "network": row["network"],
            "wallet_qr_photo_id": row["qr_photo_id"],
            "wallet_id": row["id"],
            "saved_address_id": row["id"],
            "address_from_saved": True,
            "return_to_order": True,
        }
        if preserved["amount_usdt"] is not None:
            update["amount_usdt"] = preserved["amount_usdt"]
        await state.update_data(**update)
        await message.answer(
            "✅ تم حفظ المحفظة وQR وتوثيقهما. سيتم استخدامهما تلقائياً في هذا الطلب والطلبات القادمة."
            if lang == "ar" else
            "✅ The wallet and QR were saved and verified. They will be reused automatically."
        )
        from handlers.order_wallet_policy import _continue_to_currency
        await _continue_to_currency(message, state, lang)
        return

    await message.answer(
        "✅ تم حفظ العنوان وتوثيقه. 🔒 لا يمكن تعديله؛ يمكن حذفه وإضافة عنوان جديد فقط."
        if lang == "ar" else
        "✅ Address saved and verified. 🔒 It cannot be edited; delete it and add a new address to change it."
    )
