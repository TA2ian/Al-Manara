"""Start and terms handlers."""
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import TermsStates
from keyboards.inline import terms_keyboard, main_menu_inline
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from database import get_pool
from config import Config

router = Router()


TERMS_TEXT_AR = """📋 <b>شروط الخدمة وإخلاء المسؤولية</b>

مرحباً بك في بوت USDT!

▪️ هذا البوت وسيط بينك وبين مزود الخدمة.
▪️ جميع المعاملات نهائية ولا يمكن التراجع.
▪️ تأكد من صحة عنوان محفظتك قبل الإرسال.
▪️ نحن غير مسؤولين عن فقدان الأموال بسبب عنوان خاطئ أو شبكة غير صحيحة.
▪️ سعر الصرف قابل للتغيير دون إشعار مسبق.
▪️ الحد الأدنى للطلب: {min_order} USDT.
▪️ الحد الأقصى للطلب: {max_order} USDT.
▪️ مدة المعالجة: 15 دقيقة - 24 ساعة.
▪️ الدفع عبر شام كاش فقط.
▪️ يجب إرسال إيصال الدفع خلال {timeout} دقيقة.

<b>بالضغط على "أوافق" فإنك تقر بأنك قرأت وفهمت هذه الشروط.</b>"""


WELCOME_TEXT_AR = """🎉 <b>أهلاً وسهلاً يا {name}!</b>

تم تفعيل حسابك بنجاح ✅

يمكنك الآن:
💰 إنشاء طلب شحن USDT جديد
📋 متابعة طلباتك السابقة

اضغط على الأزرار أدناه 👇"""


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

    # If user exists and accepted terms
    if user and user['terms_accepted']:
        await message.answer(
            WELCOME_TEXT_AR.format(name=message.from_user.first_name),
            reply_markup=main_menu_inline('ar'),
            parse_mode='HTML'
        )
        await message.answer(
            "👇",
            reply_markup=compact_reply_keyboard('ar')
        )
        return

    # Show terms
    lang = message.from_user.language_code or 'ar'
    if lang not in ['ar', 'en']:
        lang = 'ar'

    terms_text = TERMS_TEXT_AR.format(
        min_order=Config.MIN_ORDER,
        max_order=Config.MAX_ORDER,
        timeout=Config.PAYMENT_TIMEOUT
    )

    await message.answer(
        terms_text,
        reply_markup=terms_keyboard(lang),
        parse_mode='HTML'
    )

    await state.set_state(TermsStates.waiting_acceptance)
    await state.update_data(language=lang)


@router.callback_query(TermsStates.waiting_acceptance, F.data == "accept_terms")
async def accept_terms(callback: CallbackQuery, state: FSMContext):
    """Handle terms acceptance."""
    data = await state.get_data()
    lang = data.get('language', 'ar')

    pool = await get_pool()

    async with pool.acquire() as conn:
        username = callback.from_user.username or ''
        await conn.execute("""
            INSERT INTO users (telegram_id, username, language, terms_accepted, terms_accepted_at)
            VALUES ($1, $2, $3, TRUE, NOW())
            ON CONFLICT (telegram_id) DO UPDATE SET
                terms_accepted = TRUE,
                terms_accepted_at = NOW()
        """, callback.from_user.id, username, lang)

    # Send welcome message
    await callback.message.delete()

    await callback.message.answer(
        WELCOME_TEXT_AR.format(name=callback.from_user.first_name),
        reply_markup=main_menu_inline(lang),
        parse_mode='HTML'
    )

    await callback.message.answer(
        "👇",
        reply_markup=compact_reply_keyboard(lang)
    )

    await state.clear()
    await callback.answer()


@router.callback_query(TermsStates.waiting_acceptance, F.data == "decline_terms")
async def decline_terms(callback: CallbackQuery, state: FSMContext):
    """Handle terms decline."""
    data = await state.get_data()
    lang = data.get('language', 'ar')

    await callback.message.edit_text(
        locale_service.get('declined_message', lang),
        parse_mode='HTML'
    )

    await state.clear()
    await callback.answer()
