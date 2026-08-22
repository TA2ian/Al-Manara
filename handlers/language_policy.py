"""Customer language switching policy.

This router owns the language-switch callbacks before the legacy menu router.
It always reads the current language from the database, never assumes Arabic,
and clears an in-progress FSM flow when the language changes to prevent mixed-language steps.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database import get_pool
from services.locale_service import locale_service
from keyboards.inline import main_menu_inline
from keyboards.reply import compact_reply_keyboard

router = Router()


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇸🇦 العربية", callback_data="policy_set_lang_ar"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="policy_set_lang_en"),
        ]
    ])


async def _get_lang(user_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id=$1", user_id)
    return (row["language"] if row and row["language"] in ("ar", "en") else "ar")


async def _show_prompt(message, lang: str):
    text = (
        "🌐 <b>اختيار اللغة</b>\n\nاختر اللغة التي تريد استخدامها في البوت.\n"
        "سيتم استخدام اللغة المختارة في جميع الرسائل والخطوات التالية."
        if lang == "ar" else
        "🌐 <b>Choose Language</b>\n\nSelect the language you want to use in the bot.\n"
        "The selected language will be used for all following messages and steps."
    )
    await message.edit_text(text, reply_markup=language_keyboard(), parse_mode="HTML")


@router.message(F.text.in_(["/language", "/lang"]))
async def language_command(message: Message):
    lang = await _get_lang(message.from_user.id)
    await message.answer(
        (
            "🌐 <b>اختيار اللغة</b>\n\nاختر اللغة التي تريد استخدامها في البوت."
            if lang == "ar" else
            "🌐 <b>Choose Language</b>\n\nSelect the language you want to use in the bot."
        ),
        reply_markup=language_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "quick_change_lang")
async def language_prompt(callback: CallbackQuery, state: FSMContext):
    lang = await _get_lang(callback.from_user.id)
    await _show_prompt(callback.message, lang)
    await callback.answer()


@router.callback_query(F.data.startswith("policy_set_lang_"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    new_lang = callback.data.replace("policy_set_lang_", "")
    if new_lang not in ("ar", "en"):
        await callback.answer("Invalid language", show_alert=True)
        return

    old_lang = await _get_lang(callback.from_user.id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET language=$1 WHERE telegram_id=$2",
            new_lang, callback.from_user.id,
        )

    # Do not leave an old Arabic/English FSM step active after a language switch.
    # Restarting from the main menu guarantees the next flow uses one language only.
    await state.clear()

    text = (
        "✅ <b>تم تغيير اللغة إلى العربية.</b>\n\n"
        "تم إنهاء أي خطوة غير مكتملة حتى لا تختلط اللغات. يمكنك بدء العملية من القائمة."
        if new_lang == "ar" else
        "✅ <b>Language changed to English.</b>\n\n"
        "Any unfinished step was cleared to prevent mixed-language messages. You can restart from the menu."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.message.answer(
        locale_service.get("main_menu", new_lang),
        reply_markup=main_menu_inline(new_lang),
    )
    await callback.message.answer("👇", reply_markup=compact_reply_keyboard(new_lang))
    await callback.answer()
