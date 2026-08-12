"""Verification handlers for user account verification."""
import html
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import VerificationStates
from keyboards.inline import main_menu_inline, start_verification_keyboard, admin_verify_keyboard
from keyboards.reply import compact_reply_keyboard, phone_share_keyboard
from services.locale_service import locale_service
from config import Config
from database import get_pool

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "start_verification")
async def start_verification(callback: CallbackQuery, state: FSMContext):
    """Start mandatory account verification."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            callback.from_user.id
        )

    if not user:
        await callback.answer("الرجاء البدء أولاً: /start", show_alert=True)
        return

    lang = user['language'] or 'ar'
    await state.clear()
    await callback.message.edit_text(
        locale_service.get('verification_prompt', lang),
        parse_mode='HTML'
    )

    if not user.get('phone_verified'):
        await callback.message.answer(
            "📱 <b>الخطوة 1 من 4: رقم الهاتف</b>\n\n"
            "يجب مشاركة رقم الهاتف من حساب Telegram نفسه لإكمال التوثيق."
            if lang == 'ar' else
            "📱 <b>Step 1 of 4: Phone number</b>\n\n"
            "You must share the phone number from this Telegram account to complete verification.",
            reply_markup=phone_share_keyboard(lang),
            parse_mode='HTML'
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
        await conn.execute(
            "UPDATE users SET phone_number=$1, phone_verified=TRUE WHERE telegram_id=$2",
            phone, message.from_user.id
        )

    await _ask_full_name(message, state, lang)


@router.message(VerificationStates.waiting_phone)
async def reject_manual_phone(message: Message, state: FSMContext):
    """Do not accept a typed phone number for mandatory verification."""
    lang = await _user_lang(message.from_user.id)
    await message.answer(
        "❌ يجب مشاركة رقم الهاتف باستخدام زر <b>مشاركة رقم الهاتف</b>، وليس كتابته يدوياً."
        if lang == 'ar' else
        "❌ You must share your phone using the <b>Share phone number</b> button; typed numbers are not accepted.",
        reply_markup=phone_share_keyboard(lang),
        parse_mode='HTML'
    )


async def _ask_full_name(message: Message, state: FSMContext, lang: str):
    await message.answer(
        "📛 <b>الخطوة 2 من 4: الاسم الكامل</b>\n\nأدخل اسمك الكامل كما هو مرتبط بحساب ShamCash."
        if lang == 'ar' else
        "📛 <b>Step 2 of 4: Full name</b>\n\nEnter your full name as associated with your ShamCash account.",
        parse_mode='HTML'
    )
    await state.set_state(VerificationStates.waiting_full_name)


async def _user_lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id=$1", telegram_id)
    return (row['language'] if row else 'ar') or 'ar'


@router.message(VerificationStates.waiting_full_name)
async def enter_full_name(message: Message, state: FSMContext):
    """Handle full name input."""
    name = (message.text or '').strip()
    if len(name) < 3 or len(name) > 100:
        await message.answer("📛 الاسم يجب أن يكون بين 3 و100 حرف. أعد المحاولة:")
        return

    await state.update_data(full_name=name)
    lang = await _user_lang(message.from_user.id)
    await message.answer(
        "💳 <b>الخطوة 3 من 4: حساب ShamCash</b>\n\nأدخل اسم المستخدم/رقم الحساب كما يظهر في ShamCash."
        if lang == 'ar' else
        "💳 <b>Step 3 of 4: ShamCash account</b>\n\nEnter the ShamCash username/account identifier.",
        parse_mode='HTML'
    )
    await state.set_state(VerificationStates.waiting_shamcash_account)


@router.message(VerificationStates.waiting_shamcash_account)
async def enter_shamcash(message: Message, state: FSMContext):
    """Handle ShamCash account input."""
    account = (message.text or '').strip()
    lang = await _user_lang(message.from_user.id)
    if len(account) < 5 or len(account) > 100:
        await message.answer(
            "❌ بيانات حساب ShamCash غير صالحة. أعد إدخالها."
            if lang == 'ar' else
            "❌ Invalid ShamCash account data. Please enter it again."
        )
        return

    await state.update_data(shamcash_account=account)
    await message.answer(
        "📸 <b>الخطوة 4 من 4: QR شام كاش</b>\n\nأرسل QR لحساب ShamCash نفسه. هذا الحقل إلزامي للتحقق من تطابق الحساب.\n\n❗ لا يوجد خيار تخطي."
        if lang == 'ar' else
        "📸 <b>Step 4 of 4: ShamCash QR</b>\n\nSend the QR for the same ShamCash account. This is mandatory for account matching.\n\n❗ Skipping is not allowed.",
        parse_mode='HTML'
    )
    await state.set_state(VerificationStates.waiting_shamcash_qr)


@router.message(VerificationStates.waiting_shamcash_qr, F.photo)
async def upload_shamcash_qr(message: Message, state: FSMContext):
    """Handle mandatory ShamCash QR photo."""
    photo_id = message.photo[-1].file_id
    await state.update_data(shamcash_qr_photo_id=photo_id)
    await submit_verification(message, state)


@router.message(VerificationStates.waiting_shamcash_qr)
async def reject_missing_shamcash_qr(message: Message, state: FSMContext):
    """Reject anything other than a QR image during verification."""
    lang = await _user_lang(message.from_user.id)
    await message.answer(
        "❌ يجب إرسال صورة QR لحساب ShamCash. لا يمكن تخطي هذه الخطوة."
        if lang == 'ar' else
        "❌ You must send a ShamCash QR image. This step cannot be skipped."
    )


async def submit_verification(msg: Message, state: FSMContext):
    """Submit verification request and notify admins."""
    data = await state.get_data()
    full_name = data['full_name']
    shamcash_account = data['shamcash_account']
    shamcash_qr_photo_id = data.get('shamcash_qr_photo_id')

    if not shamcash_qr_photo_id:
        await msg.answer("❌ لا يمكن إرسال طلب التوثيق بدون QR شام كاش.")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            msg.chat.id
        )
        if user:
            await conn.execute(
                """UPDATE users
                   SET full_name = $1, shamcash_account = $2,
                       shamcash_qr_photo_id = $3,
                       verification_status = 'pending', is_verified = FALSE
                   WHERE telegram_id = $4""",
                full_name, shamcash_account, shamcash_qr_photo_id, msg.chat.id
            )

    if not user:
        return

    lang = user['language'] or 'ar'
    bot = Bot(token=Config.BOT_TOKEN)

    verify_kb = admin_verify_keyboard(msg.chat.id, full_name, shamcash_account)
    admin_text = (
        f"🔔 <b>طلب توثيق جديد</b>\n\n"
        f"👤 المستخدم: @{html.escape(msg.chat.username or 'بدون')}\n"
        f"🆔 ID: <code>{msg.chat.id}</code>\n"
        f"📱 الهاتف: <code>{html.escape(data.get('phone_number') or 'محفوظ في الحساب')}</code>\n"
        f"📛 الاسم: {html.escape(full_name)}\n"
        f"💳 شام كاش: <code>{html.escape(shamcash_account)}</code>\n\n"
        f"اختر إجراء:"
    )

    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=verify_kb, parse_mode='HTML')
            await bot.send_photo(
                admin_id,
                shamcash_qr_photo_id,
                caption=f"📸 QR لحساب شام كاش للمستخدم {html.escape(full_name)}"
            )
        except Exception as e:
            logger.error("Failed to notify admin %s: %s", admin_id, e)

    await msg.answer(
        locale_service.get('verification_submitted', lang),
        reply_markup=main_menu_inline(lang)
    )
    await msg.answer("👇", reply_markup=compact_reply_keyboard(lang))
    await state.clear()
