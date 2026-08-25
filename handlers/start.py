"""Start and terms handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import TermsStates
from keyboards.inline import terms_keyboard, main_menu_inline, language_select_keyboard
from keyboards.reply import compact_reply_keyboard, remove_dashboard_keyboard
from services.locale_service import locale_service
from services.legal_policy import get_start_terms_text
from database import get_pool
from config import Config

router = Router()


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start and make it an explicit dashboard reset boundary."""
    pool = await get_pool()
    username = message.from_user.username or ""
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", message.from_user.id)
        if user:
            await conn.execute("UPDATE users SET username=$1 WHERE telegram_id=$2", username, message.from_user.id)
    await state.clear()
    if user and user["terms_accepted"]:
        lang = user["language"] or "ar"
        await message.answer(locale_service.get("welcome", lang, name=message.from_user.first_name), reply_markup=main_menu_inline(lang), parse_mode="HTML")
        await message.answer("👇", reply_markup=compact_reply_keyboard(lang))
        return
    await message.answer("🌐", reply_markup=language_select_keyboard())
    await state.set_state(TermsStates.waiting_acceptance)


@router.callback_query(TermsStates.waiting_acceptance, F.data.in_(["lang_ar", "lang_en"]))
async def select_start_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("lang_", "")
    await callback.message.edit_text(
        get_start_terms_text(lang, Config.PAYMENT_TIMEOUT),
        reply_markup=terms_keyboard(lang),
        parse_mode="HTML",
    )
    await state.update_data(language=lang)
    await callback.answer()


@router.callback_query(TermsStates.waiting_acceptance, F.data == "accept_terms")
async def accept_terms(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "ar")
    pool = await get_pool()
    username = callback.from_user.username or ""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (telegram_id, username, language, terms_accepted, terms_accepted_at, verification_status)
            VALUES ($1, $2, $3, TRUE, NOW(), 'not_verified')
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                language = EXCLUDED.language,
                terms_accepted = TRUE,
                terms_accepted_at = NOW(),
                verification_status = CASE
                    WHEN users.is_verified THEN users.verification_status
                    WHEN users.verification_status = 'pending'
                         AND users.phone_verified
                         AND users.phone_number IS NOT NULL
                         AND users.full_name IS NOT NULL
                         AND users.shamcash_account IS NOT NULL
                         AND users.shamcash_qr_photo_id IS NOT NULL
                    THEN users.verification_status
                    WHEN users.verification_status IN ('approved', 'rejected') THEN users.verification_status
                    ELSE 'not_verified'
                END
            """,
            callback.from_user.id,
            username,
            lang,
        )
    await callback.message.delete()
    await callback.message.answer(locale_service.get("welcome", lang, name=callback.from_user.first_name), reply_markup=main_menu_inline(lang), parse_mode="HTML")
    await callback.message.answer("👇", reply_markup=compact_reply_keyboard(lang))
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "decline_terms")
async def decline_terms(callback: CallbackQuery, state: FSMContext):
    """Reject terms reliably even if the FSM state was lost."""
    data = await state.get_data()
    lang = data.get("language")
    if not lang:
        pool = await get_pool()
        async with pool.acquire() as conn:
            lang = await conn.fetchval("SELECT language FROM users WHERE telegram_id=$1", callback.from_user.id) or "ar"
    await callback.message.edit_text(locale_service.get("declined_message", lang), parse_mode="HTML")
    await callback.message.answer("", reply_markup=remove_dashboard_keyboard())
    await state.clear()
    await callback.answer("❌ تم الرفض" if lang == "ar" else "❌ Declined")
