"""Start and terms handlers."""
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import TermsStates
from keyboards.inline import terms_keyboard, main_menu_inline, language_select_keyboard
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from database import get_pool
from config import Config

router = Router()


TERMS_TEXT_AR = """━━━ <b>شروط الخدمة وإخلاء المسؤولية</b> ━━━

<b>أولاً: طبيعة الخدمة</b>
يعمل هذا البوت كوسيط تقني بينك وبين مزود خدمة تحويل العملات الرقمية. البوت هو واجهة لإدارة الطلبات فقط.

<b>ثانياً: المسؤولية</b>
- أنت وحدك المسؤول عن صحة عنوان محفظة USDT الذي تُدخله.
- نحن غير مسؤولين عن فقدان الأموال نتيجة إدخال عنوان خاطئ أو اختيار شبكة غير صحيحة.
- عند حفظ عنوان محفظة، تقع عليك مسؤولية التحقق منه قبل كل استخدام.
- البوت لا يخزن العملات الرقمية ولا يتعامل بها بشكل مباشر.

<b>ثالثاً: المعاملات</b>
- الحد الأدنى للطلب: {min_order} USDT.
- الحد الأقصى للطلب: {max_order} USDT.
- سعر الصرف قابل للتغيير دون إشعار مسبق.
- مدة المعالجة المتوقعة: 15 دقيقة - 24 ساعة.
- الدفع عبر شام كاش حصراً.
- يجب إرفاق إيصال الدفع خلال {timeout} دقيقة من الموافقة على الطلب.
- جميع المعاملات نهائية بعد تأكيد الدفع.

<b>رابعاً: الخصوصية</b>
- تُستخدم بياناتك (الاسم، رقم شام كاش، معرف تيليغرام) لأغراض إدارة الطلبات فقط.
- لا يتم مشاركة بياناتك مع أطراف ثالثة.

<b>خامساً: أحكام عامة</b>
- نحتفظ بالحق في رفض أو إلغاء أي طلب وفقاً لتقديرنا.
- نحتفظ بالحق في تحديث هذه الشروط في أي وقت.
- استخدامك المستمر للبوت بعد التحديث يعني موافقتك على الشروط الجديدة.

━━━━━━━━━━━━━━━━━━━━
<b>بالضغط على "أوافق" فإنك تقر بأنك قرأت وفهمت وأقريت هذه الشروط.</b>"""


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
        lang = user['language'] or 'ar'
        await message.answer(
            locale_service.get('welcome', lang, name=message.from_user.first_name),
            reply_markup=main_menu_inline(lang),
            parse_mode='HTML'
        )
        await message.answer(
            "👇",
            reply_markup=compact_reply_keyboard(lang)
        )
        return

    # Show language selection first
    await message.answer(
        locale_service.get('select_language', 'ar'),
        reply_markup=language_select_keyboard()
    )

    await state.set_state(TermsStates.waiting_acceptance)


@router.callback_query(TermsStates.waiting_acceptance, F.data.in_(["lang_ar", "lang_en"]))
async def select_start_language(callback: CallbackQuery, state: FSMContext):
    """Handle language selection at start."""
    lang = callback.data.replace("lang_", "")

    terms_text = (
        TERMS_TEXT_AR if lang == 'ar' else
        "━━━ <b>Terms of Service & Disclaimer</b> ━━━\n\n"
        "<b>1. Service Nature</b>\n"
        "This bot serves as a technical intermediary between you and the digital currency exchange service provider. The bot is an order management interface only.\n\n"
        "<b>2. Liability</b>\n"
        "- You are solely responsible for the accuracy of the USDT wallet address you enter.\n"
        "- We are not liable for any loss of funds resulting from an incorrect address or wrong network selection.\n"
        "- When saving a wallet address, you bear the responsibility of verifying it before each use.\n"
        "- The bot does not store or directly handle digital currencies.\n\n"
        "<b>3. Transactions</b>\n"
        "- Minimum order: {min_order} USDT.\n"
        "- Maximum order: {max_order} USDT.\n"
        "- Exchange rates are subject to change without prior notice.\n"
        "- Estimated processing time: 15 minutes - 24 hours.\n"
        "- Payment via Sham Cash only.\n"
        "- Payment receipt must be submitted within {timeout} minutes of order approval.\n"
        "- All transactions are final once payment is confirmed.\n\n"
        "<b>4. Privacy</b>\n"
        "- Your data (name, Sham Cash account, Telegram ID) is used solely for order management.\n"
        "- Your data is not shared with third parties.\n\n"
        "<b>5. General Provisions</b>\n"
        "- We reserve the right to reject or cancel any order at our discretion.\n"
        "- We reserve the right to update these terms at any time.\n"
        "- Your continued use of the bot after updates constitutes acceptance of the new terms.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>By clicking \"Agree\", you acknowledge that you have read, understood, and accepted these terms.</b>"
    )

    await callback.message.edit_text(
        terms_text.format(
            min_order=Config.MIN_ORDER,
            max_order=Config.MAX_ORDER,
            timeout=Config.PAYMENT_TIMEOUT
        ),
        reply_markup=terms_keyboard(lang),
        parse_mode='HTML'
    )

    await state.update_data(language=lang)
    await callback.answer()


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
        locale_service.get('welcome', lang, name=callback.from_user.first_name),
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
