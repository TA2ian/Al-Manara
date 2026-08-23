"""Canonical customer verification flow.

The customer submits the ShamCash receiving address and its QR as one
verification input: either QR-only, where the address is extracted from the
QR, or QR with an address caption, where both values must match.
"""
import html
import io
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from PIL import Image

from config import Config
from database import get_pool
from keyboards.inline import main_menu_inline
from keyboards.reply import compact_reply_keyboard, phone_share_keyboard
from services.locale_service import locale_service
from states import VerificationStates

logger = logging.getLogger(__name__)
router = Router()


def _normalize_shamcash_value(value: str) -> str:
    normalized = (value or "").strip()
    for prefix in ("shamcash:", "shamcash://"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    return normalized


def _decode_qr(payload: bytes) -> str:
    try:
        from pyzbar.pyzbar import decode as qr_decode
        decoded = qr_decode(Image.open(io.BytesIO(payload)))
        if not decoded:
            return ""
        return decoded[0].data.decode("utf-8", errors="strict").strip()
    except Exception:
        logger.exception("Failed to decode ShamCash verification QR")
        return ""


async def _user_lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id=$1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


@router.callback_query(F.data == "start_verification")
async def start_verification(callback: CallbackQuery, state: FSMContext):
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", callback.from_user.id)
    if not user:
        await callback.answer("❌ الرجاء البدء أولاً: /start" if (await _user_lang(callback.from_user.id)) == "ar" else "❌ Please start the bot first: /start", show_alert=True)
        return

    lang = user["language"] or "ar"
    await state.clear()
    requirements = (
        "🔒 <b>متطلبات التوثيق</b>\n\n"
        "1️⃣ <b>رقم الهاتف:</b> شاركه من حساب Telegram نفسه.\n\n"
        "2️⃣ <b>الاسم الكامل:</b> يجب أن يطابق الاسم المرتبط بحساب ShamCash.\n\n"
        "3️⃣ <b>حساب ShamCash:</b> أرسل <b>صورة QR لحساب الاستلام</b> فقط، أو أرسل الصورة مع <b>عنوان/رقم الحساب في وصف الصورة</b>.\n\n"
        "سيتم استخراج العنوان من QR عند إرساله وحده، أو مطابقة العنوان المرفق مع القيمة الموجودة داخل QR عند إرسالهما معاً.\n\n"
        "⚠️ لا يمكن إرسال طلب التوثيق إذا تعذر قراءة QR أو لم تتطابق القيمتان.\n\n"
        "📋 بعد الإرسال تتم مراجعة البيانات من الإدارة قبل تفعيل الحساب."
        if lang == "ar" else
        "🔒 <b>Verification requirements</b>\n\n"
        "1️⃣ <b>Phone number:</b> share it from this Telegram account.\n\n"
        "2️⃣ <b>Full name:</b> it must match the name associated with your ShamCash account.\n\n"
        "3️⃣ <b>ShamCash account:</b> send the <b>receiving-account QR image</b> only, or send the image with the <b>account address/number in its caption</b>.\n\n"
        "The account address is extracted from QR when QR is sent alone, or the caption is matched against the QR value when both are provided.\n\n"
        "⚠️ Verification cannot be submitted if QR cannot be decoded or the two values do not match.\n\n"
        "📋 The data is reviewed by the admin team before account activation."
    )
    await callback.message.edit_text(requirements, parse_mode="HTML")

    if not user.get("phone_verified"):
        await callback.message.answer(
            "📱 <b>الخطوة 1 من 3: رقم الهاتف</b>\n\nشارك رقم هاتفك باستخدام زر المشاركة من حساب Telegram نفسه."
            if lang == "ar" else
            "📱 <b>Step 1 of 3: Phone number</b>\n\nShare your phone number using the Telegram account's share button.",
            reply_markup=phone_share_keyboard(lang),
            parse_mode="HTML",
        )
        await state.set_state(VerificationStates.waiting_phone)
    else:
        await _ask_full_name(callback.message, state, lang)
    await callback.answer()


@router.message(VerificationStates.waiting_phone, F.contact)
async def receive_phone(message: Message, state: FSMContext):
    contact = message.contact
    lang = await _user_lang(message.from_user.id)
    if contact.user_id != message.from_user.id:
        await message.answer("❌ يجب مشاركة رقم هاتفك أنت من حساب Telegram نفسه." if lang == "ar" else "❌ Share your own phone number from this Telegram account.")
        return
    phone = (contact.phone_number or "").strip()
    if not phone:
        await message.answer("❌ تعذر قراءة رقم الهاتف. أعد المشاركة." if lang == "ar" else "❌ Could not read the phone number. Please share it again.")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET phone_number=$1, phone_verified=TRUE WHERE telegram_id=$2", phone, message.from_user.id)
    await state.update_data(phone_number=phone)
    await _ask_full_name(message, state, lang)


@router.message(VerificationStates.waiting_phone)
async def reject_manual_phone(message: Message):
    lang = await _user_lang(message.from_user.id)
    await message.answer(
        "❌ يجب مشاركة رقم الهاتف باستخدام زر <b>مشاركة رقم الهاتف</b>، وليس كتابته يدوياً."
        if lang == "ar" else
        "❌ You must share your phone using the <b>Share phone number</b> button; typed numbers are not accepted.",
        reply_markup=phone_share_keyboard(lang),
        parse_mode="HTML",
    )


async def _ask_full_name(message: Message, state: FSMContext, lang: str):
    await message.answer(
        "📛 <b>الخطوة 2 من 3: الاسم الكامل</b>\n\nأدخل اسمك الكامل كما هو مرتبط بحساب ShamCash."
        if lang == "ar" else
        "📛 <b>Step 2 of 3: Full name</b>\n\nEnter your full name as associated with your ShamCash account.",
        parse_mode="HTML",
    )
    await state.set_state(VerificationStates.waiting_full_name)


@router.message(VerificationStates.waiting_full_name)
async def enter_full_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    lang = await _user_lang(message.from_user.id)
    if len(name) < 3 or len(name) > 100:
        await message.answer("📛 الاسم يجب أن يكون بين 3 و100 حرف. أعد المحاولة:" if lang == "ar" else "📛 The name must be between 3 and 100 characters. Please try again:")
        return
    await state.update_data(full_name=name)
    await message.answer(
        "💳 <b>الخطوة 3 من 3: حساب ShamCash</b>\n\nأرسل <b>صورة QR</b> لحساب الاستلام فقط، أو أرسل صورة QR مع عنوان/رقم الحساب في وصف الصورة.\n\nسيتم استخراج العنوان من QR أو مطابقة العنوان المرفق معه تلقائياً."
        if lang == "ar" else
        "💳 <b>Step 3 of 3: ShamCash account</b>\n\nSend the <b>receiving-account QR image</b> only, or send the QR image with the account address/number in its caption.\n\nThe address will be extracted from QR or matched against the caption automatically.",
        parse_mode="HTML",
    )
    await state.set_state(VerificationStates.waiting_shamcash_identity)


@router.message(VerificationStates.waiting_shamcash_identity, F.photo)
async def receive_shamcash_identity(message: Message, state: FSMContext):
    lang = await _user_lang(message.from_user.id)
    raw = io.BytesIO()
    try:
        await message.bot.download(file=message.photo[-1].file_id, destination=raw)
    except Exception:
        logger.exception("Failed to download ShamCash verification QR")
        await message.answer("❌ تعذر قراءة صورة QR. أعد إرسالها بوضوح." if lang == "ar" else "❌ Could not read the QR image. Please send it again clearly.")
        return

    qr_value = _normalize_shamcash_value(_decode_qr(raw.getvalue()))
    if not qr_value or len(qr_value) < 5 or len(qr_value) > 100:
        await message.answer(
            "❌ لم أتمكن من استخراج عنوان ShamCash صالح من QR. أرسل QR واضحاً من تطبيق ShamCash."
            if lang == "ar" else
            "❌ I could not extract a valid ShamCash receiving address from the QR. Send a clear QR from the ShamCash app."
        )
        return

    caption = _normalize_shamcash_value(message.caption or "")
    if caption and (len(caption) < 5 or len(caption) > 100):
        await message.answer("❌ العنوان المرفق غير صالح. أرسل QR فقط أو QR مع عنوان ShamCash الصحيح." if lang == "ar" else "❌ The attached ShamCash address is invalid. Send QR only or QR with the correct address.")
        return

    if caption and caption.casefold() != qr_value.casefold():
        await message.answer(
            "❌ عنوان ShamCash المرفق لا يطابق العنوان المستخرج من QR. أرسل QR والعنوان الصحيحين معاً."
            if lang == "ar" else
            "❌ The ShamCash address in the caption does not match the address encoded in the QR. Send the matching QR and address together."
        )
        return

    await state.update_data(
        shamcash_account=qr_value,
        shamcash_qr_photo_id=message.photo[-1].file_id,
    )
    await submit_verification(message, state)


@router.message(VerificationStates.waiting_shamcash_identity)
async def reject_non_qr_shamcash_input(message: Message):
    lang = await _user_lang(message.from_user.id)
    await message.answer(
        "❌ أرسل صورة QR لحساب الاستلام في ShamCash. يمكنك إرسال QR وحده أو QR مع العنوان في وصف الصورة."
        if lang == "ar" else
        "❌ Send the ShamCash receiving-account QR image. You may send QR alone or QR with the address in the caption."
    )


async def submit_verification(msg: Message, state: FSMContext):
    data = await state.get_data()
    full_name = (data.get("full_name") or "").strip()
    shamcash_account = (data.get("shamcash_account") or "").strip()
    shamcash_qr_photo_id = data.get("shamcash_qr_photo_id")
    lang = await _user_lang(msg.chat.id)

    if not full_name or not shamcash_account or not shamcash_qr_photo_id:
        await msg.answer("❌ بيانات التوثيق غير مكتملة." if lang == "ar" else "❌ Verification data is incomplete.")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", msg.chat.id)
        if not user:
            return
        if not user["phone_verified"] or not user["phone_number"]:
            await msg.answer("❌ يجب توثيق رقم الهاتف أولاً." if lang == "ar" else "❌ Your phone number must be verified first.")
            return
        if user["verification_status"] == "pending":
            await msg.answer("⏳ طلب التوثيق الحالي قيد المراجعة بالفعل." if lang == "ar" else "⏳ Your current verification request is already under review.")
            await state.clear()
            return
        await conn.execute(
            """UPDATE users SET full_name=$1, shamcash_account=$2, shamcash_qr_photo_id=$3,
               verification_status='pending', is_verified=FALSE WHERE telegram_id=$4""",
            full_name, shamcash_account, shamcash_qr_photo_id, msg.chat.id,
        )
        await conn.execute(
            """INSERT INTO audit_logs (user_id, action, details, severity)
               VALUES ($1, 'verification_submitted', $2, 'info')""",
            user["id"], "phone_verified=true; shamcash_address_from_qr=true; shamcash_qr_present=true",
        )

    bot = Bot(token=Config.BOT_TOKEN)
    admin_text = (
        f"🔔 <b>طلب توثيق جديد</b>\n\n"
        f"👤 المستخدم: @{html.escape(msg.chat.username or 'بدون')}\n"
        f"🆔 ID: <code>{msg.chat.id}</code>\n"
        f"📱 الهاتف: <code>{html.escape(user['phone_number'] or 'N/A')}</code>\n"
        f"📛 الاسم: {html.escape(full_name)}\n"
        f"💳 شام كاش: <code>{html.escape(shamcash_account)}</code>\n\n"
        "⚠️ راجع QR والعنوان المحفوظ قبل الموافقة."
    )
    review_keyboard = [[
        {"text": "✅ توثيق", "callback_data": f"verify_approve_{msg.chat.id}"},
        {"text": "❌ رفض", "callback_data": f"verify_reject_{msg.chat.id}"},
    ]]
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    review_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(**button) for button in row] for row in review_keyboard])
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=review_markup, parse_mode="HTML")
            await bot.send_photo(admin_id, shamcash_qr_photo_id, caption=f"📸 QR لحساب الاستلام في ShamCash للمستخدم {html.escape(full_name)}")
        except Exception:
            logger.exception("Failed to notify verification admin %s", admin_id)

    await msg.answer(
        "✅ تم إرسال بيانات التوثيق للمراجعة. سيتم إبلاغك بالنتيجة بعد مراجعة الإدارة."
        if lang == "ar" else
        "✅ Your verification details were submitted for review. You will be notified after the admin review."
    )
    await state.clear()
