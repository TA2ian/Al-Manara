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

    # Show bot intro before language selection
    await message.answer(
        locale_service.get('bot_intro', 'ar'),
        parse_mode='HTML'
    )

    # Show language selection
    await message.answer(
        locale_service.get('select_language', 'ar'),
        reply_markup=language_select_keyboard()
    )

    await state.set_state(TermsStates.waiting_acceptance)


@router.callback_query(TermsStates.waiting_acceptance, F.data.in_(["lang_ar", "lang_en"]))
async def select_start_language(callback: CallbackQuery, state: FSMContext):
    """Handle language selection at start."""
    lang = callback.data.replace("lang_", "")

    await callback.message.edit_text(
        locale_service.get('terms_text', lang,
                          min_order=Config.MIN_ORDER,
                          max_order=Config.MAX_ORDER,
                          timeout=Config.PAYMENT_TIMEOUT),
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
