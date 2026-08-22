"""Verification handlers for user account verification."""
import html
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import VerificationStates
from keyboards.inline import main_menu_inline
from keyboards.reply import compact_reply_keyboard, phone_share_keyboard
from services.locale_service import locale_service
from config import Config
from database import get_pool

logger = logging.getLogger(__name__)
router = Router()


async def _user_lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id=$1", telegram_id)
    return (row['language'] if row else 'ar') or 'ar'


@router.callback_query(F.data == "start_verification")
async def start_verification(callback: CallbackQuery, state: FSMContext):
    """Explain requirements first, then start mandatory account verification."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", callback.from_user.id)
    if not user:
        lang = await _user_lang(callback.from_user.id)
        alert = "❌ الرجاء البدء أولاً: /start" if lang == 'ar' else "❌ Please start the bot first: /start"
        await callback.answer(alert, show_alert=True)
        return

    lang = user['language'] or 'ar'
    await state.clear()

    requirements = (
        "🔒 <b>متطلبات التوثيق قبل البدء</b>\n\n"
        "يرجى تجهيز المعلومات التالية أولاً:\n\n"
        "1️⃣ <b>رقم هاتفك</b>\n"
        "يجب مشاركته من حساب Telegram نفسه عبر زر مشاركة رقم الهاتف.\n\n"
        "2️⃣ <b>الاسم الكامل</b>\n"
        "يجب أن يكون الاسم مطابقاً للاسم المرتبط بحسابك في ShamCash.\n\n"
        "3️⃣ <b>رقم حساب ShamCash — عنوان الاستلام</b>\n"
        "أدخل رقم/معرّف حسابك في ShamCash، أي عنوان الاستلام الذي تستقبل عليه التحويلات. لا تعِد إدخال اسمك هنا.\n\n"
        "4️⃣ <b>صورة QR لحساب ShamCash</b>\n"
        "يجب أن تكون واضحة وتخص حساب الاستلام نفسه، وهي مطلوبة لمطابقة الحساب أثناء المراجعة.\n\n"
        "⚠️ <b>مهم:</b> لا يمكن تخطي أي من هذه المتطلبات.\n"
        "📋 بعد إرسال البيانات، تتم مراجعتها من الإدارة قبل تفعيل الحساب.\n\n"
        "إذا كانت هذه المتطلبات جاهزة لديك، سنبدأ التوثيق الآن."
    ) if lang == 'ar' else (
        "🔒 <b>Verification requirements before you start</b>\n\n"
        "Please prepare the following first:\n\n"
        "1️⃣ <b>Your phone number</b>\n"
        "It must be shared from this Telegram account using the Share Phone Number button.\n\n"
        "2️⃣ <b>Full name</b>\n"
        "It must match the name associated with your ShamCash account.\n\n"
        "3️⃣ <b>ShamCash account number — receiving address</b>\n"
        "Enter your ShamCash account number/identifier: the receiving address where you receive transfers. Do not enter your name again here.\n\n"
        "4️⃣ <b>ShamCash account QR image</b>\n"
        "It must be clear, belong to the same receiving account, and is required for account matching during review.\n\n"
        "⚠️ <b>Important:</b> None of these requirements can be skipped.\n"
        "📋 After submission, the information is reviewed by the admin before the account is activated.\n\n"
        "If you have everything ready, we will start verification now."
    )

    await callback.message.edit_text(requirements, parse_mode='HTML')

    if not user.get('phone_verified'):
        await callback.message.answer(
            "📱 <b>الخطوة 1 من 4: رقم الهاتف</b>\n\nيجب مشاركة رقم الهاتف من حساب Telegram نفسه لإكمال التوثيق."
            if lang == 'ar' else
            "📱 <b>Step 1 of 4: Phone number</b>\n\nYou must share the phone number from this Telegram account to complete verification.",
            reply_markup=phone_share_keyboard(lang), parse_mode='HTML'
        )
        await state.set_state(VerificationStates.waiting_phone)
    else:
        await _ask_full_name(callback.message, state, lang)
    await callback.answer()


@router.message(VerificationStates.waiting_phone, F.contact)
async def receive_phone(message: Message, state: FSMContext):
    """Accept only a Telegram contact belonging to the sending user."""
    contact = message.contact
    lang = await _user_lang(message.from_user.id)
    if contact.user_id != message.from_user.id:
        await message.answer(
            "❌ يجب استخدام زر مشاركة رقم الهاتف من حسابك نفسه. لا يمكن استخدام رقم شخص آخر."
            if lang == 'ar' else
            "❌ You must share the phone number from your own Telegram account. Another person's contact is not accepted."
        )
        return

    phone = (contact.phone_number or '').strip()
    if not phone:
        await message.answer(
            "❌ تعذر قراءة رقم الهاتف. أعد المشاركة باستخدام زر الهاتف."
            if lang == 'ar' else
            "❌ Could not read the phone number. Please share it again using the phone button."
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET phone_number=$1, phone_verified=TRUE WHERE telegram_id=$2", phone, message.from_user.id)
    await state.update_data(phone_number=phone)
    await _ask_full_name(message, state, lang)


@router.message(VerificationStates.waiting_phone)
async def reject_manual_phone(message: Message, state: FSMContext):
    """Do not accept a typed phone number for mandatory verification."""
    lang = await _user_lang(message.from_user.id)
    await message.answer(
        "❌ يجب مشاركة رقم الهاتف باستخدام زر <b>مشاركة رقم الهاتف</b>، وليس كتابته يدوياً."
        if lang == 'ar' else
        "❌ You must share your phone using the <b>Share phone number</b> button; typed numbers are not accepted.",
        reply_markup=phone_share_keyboard(lang), parse_mode='HTML'
    )


async def _ask_full_name(message: Message, state: FSMContext, lang: str):
    await message.answer(
        "📛 <b>الخطوة 2 من 4: الاسم الكامل</b>\n\nأدخل اسمك الكامل كما هو مرتبط بحساب ShamCash."
        if lang == 'ar' else
        "📛 <b>Step 2 of 4: Full name</b>\n\nEnter your full name as associated with your ShamCash account.",
        parse_mode='HTML'
    )
    await state.set_state(VerificationStates.waiting_full_name)


@router.message(VerificationStates.waiting_full_name)
async def enter_full_name(message: Message, state: FSMContext):
    name = (message.text or '').strip()
    lang = await _user_lang(message.from_user.id)
    if len(name) < 3 or len(name) > 100:
        await message.answer(
            "📛 الاسم يجب أن يكون بين 3 و100 حرف. أعد المحاولة:"
            if lang == 'ar' else
            "📛 The name must be between 3 and 100 characters. Please try again:"
        )
        return
    await state.update_data(full_name=name)
    await message.answer(
        "💳 <b>الخطوة 3 من 4: رقم حساب ShamCash — عنوان الاستلام</b>\n\nأدخل رقم/معرّف حسابك في ShamCash، أي عنوان الاستلام الذي تستقبل عليه التحويلات. هذا ليس اسمك."
        if lang == 'ar' else
        "💳 <b>Step 3 of 4: ShamCash account number — receiving address</b>\n\nEnter your ShamCash account number/identifier, the receiving address where you receive transfers. This is not your name.",
        parse_mode='HTML'
    )
    await state.set_state(VerificationStates.waiting_shamcash_account)


@router.message(VerificationStates.waiting_shamcash_account)
async def enter_shamcash(message: Message, state: FSMContext):
    account = (message.text or '').strip()
    lang = await _user_lang(message.from_user.id)
    if len(account) < 5 or len(account) > 100:
        await message.answer(
            "❌ رقم/معرّف حساب ShamCash غير صالح. أدخل عنوان الاستلام الصحيح كما يظهر في ShamCash."
            if lang == 'ar' else
            "❌ Invalid ShamCash account number/identifier. Enter the correct receiving address as shown in ShamCash."
        )
        return
    await state.update_data(shamcash_account=account)
    await message.answer(
        "📸 <b>الخطوة 4 من 4: QR لحساب الاستلام في ShamCash</b>\n\nأرسل صورة QR المرتبطة بنفس عنوان الاستلام الذي أدخلته في الخطوة السابقة.\n\n❗ لا يمكن تخطي هذه الخطوة."
        if lang == 'ar' else
        "📸 <b>Step 4 of 4: ShamCash receiving-account QR</b>\n\nSend the QR image linked to the same receiving address you entered in the previous step.\n\n❗ This step cannot be skipped.",
        parse_mode='HTML'
    )
    await state.set_state(VerificationStates.waiting_shamcash_qr)


@router.message(VerificationStates.waiting_shamcash_qr, F.photo)
async def upload_shamcash_qr(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(shamcash_qr_photo_id=photo_id)
    await submit_verification(message, state)


@router.message(VerificationStates.waiting_shamcash_qr)
async def reject_missing_shamcash_qr(message: Message, state: FSMContext):
    lang = await _user_lang(message.from_user.id)
    await message.answer(
        "❌ يجب إرسال صورة QR لحساب الاستلام في ShamCash. لا يمكن تخطي هذه الخطوة."
        if lang == 'ar' else
        "❌ You must send a QR image for the ShamCash receiving account. This step cannot be skipped."
    )


async def submit_verification(msg: Message, state: FSMContext):
    data = await state.get_data()
    full_name = data['full_name']
    shamcash_account = data['shamcash_account']
    shamcash_qr_photo_id = data.get('shamcash_qr_photo_id')
    phone_number = data.get('phone_number')
    lang = await _user_lang(msg.chat.id)

    if not shamcash_qr_photo_id:
        await msg.answer(
            "❌ لا يمكن إرسال طلب التوثيق بدون QR لحساب الاستلام في ShamCash."
            if lang == 'ar' else
            "❌ The verification request cannot be submitted without the ShamCash receiving-account QR."
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", msg.chat.id)
        if user:
            if not user['phone_verified'] or not user['phone_number']:
                await msg.answer(
                    "❌ يجب توثيق رقم الهاتف أولاً."
                    if lang == 'ar' else
                    "❌ Your phone number must be verified first."
                )
                return
            await conn.execute(
                """UPDATE users SET full_name=$1, shamcash_account=$2, shamcash_qr_photo_id=$3,
                   verification_status='pending', is_verified=FALSE WHERE telegram_id=$4""",
                full_name, shamcash_account, shamcash_qr_photo_id, msg.chat.id
            )
            phone_number = user['phone_number']
            await conn.execute(
                """INSERT INTO audit_logs (user_id, action, details, severity)
                   VALUES ($1, 'verification_submitted', $2, 'info')""",
                user['id'], 'phone_verified=true; shamcash_qr_present=true'
            )

    if not user:
        return

    lang = user['language'] or 'ar'
    bot = Bot(token=Config.BOT_TOKEN)
    verify_kb = _verification_review_keyboard(msg.chat.id)
    admin_text = (
        f"🔔 <b>طلب توثيق جديد</b>\n\n"
        f"👤 المستخدم: @{html.escape(msg.chat.username or 'بدون')}\n"
        f"🆔 ID: <code>{msg.chat.id}</code>\n"
        f"📱 الهاتف: <code>{html.escape(phone_number)}</code>\n"
        f"📛 الاسم: {html.escape(full_name)}\n"
        f"💳 شام كاش: <code>{html.escape(shamcash_account)}</code>\n\n"
        "⚠️ تحقق يدوي: طابق رقم/عنوان الاستلام مع QR قبل الموافقة."
    )
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=verify_kb, parse_mode='HTML')
            await bot.send_photo(admin_id, shamcash_qr_photo_id, caption=f"📸 QR لحساب الاستلام في ShamCash للمستخدم {html.escape(full_name)}")
        except Exception as e:
            logger.error("Failed to notify admin %s: %s", admin_id, e)

    await msg.answer(locale_service.get('verification_submitted', lang), reply_markup=main_menu_inline(lang))
    await msg.answer("👇", reply_markup=compact_reply_keyboard(lang))
    await state.clear()


def _verification_review_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    """Only terminal verification decisions are shown on a pending review."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ توثيق", callback_data=f"verify_approve_{telegram_id}"),
        InlineKeyboardButton(text="❌ رفض", callback_data=f"verify_reject_{telegram_id}"),
    ]])
