"""Customer support/feedback handlers with a strict media boundary."""
from __future__ import annotations

import logging
from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from database import get_pool
from keyboards.inline import cancel_keyboard
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from services.media_security import validate_image_payload, validate_pdf_payload
from services.notification_service import NotificationService
from states import FeedbackStates

logger = logging.getLogger(__name__)
router = Router()
MAX_TEXT_LENGTH = 200


async def _get_user_lang(telegram_id: int) -> str:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
            if user:
                return user["language"] or "ar"
    except Exception:
        logger.exception("Failed to fetch feedback language")
    return "ar"


@router.callback_query(F.data == "menu_feedback")
async def start_feedback(callback: CallbackQuery, state: FSMContext):
    lang = await _get_user_lang(callback.from_user.id)
    await callback.message.edit_text(locale_service.get("feedback_prompt", lang), reply_markup=cancel_keyboard(lang))
    await state.set_state(FeedbackStates.waiting_message)
    await callback.answer()


async def _store_feedback(message: Message, text: str, attachment_type: str | None, attachment_file_id: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("ALTER TABLE feedback_messages ADD COLUMN IF NOT EXISTS attachment_type TEXT")
        await conn.execute("ALTER TABLE feedback_messages ADD COLUMN IF NOT EXISTS attachment_file_id TEXT")
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", message.from_user.id)
        if not user:
            return None
        await conn.execute(
            """INSERT INTO feedback_messages (user_id, message, attachment_type, attachment_file_id)
               VALUES ($1, $2, $3, $4)""",
            user["id"], text, attachment_type, attachment_file_id,
        )
        return dict(user)


async def _notify_feedback(user: dict, text: str, attachment_type: str | None, attachment_file_id: str | None):
    from aiogram import Bot

    bot = Bot(token=Config.BOT_TOKEN)
    notification = NotificationService(bot, Config.ADMIN_IDS)
    await notification.notify_feedback(user, text, attachment_type, attachment_file_id)


@router.message(FeedbackStates.waiting_message, F.text)
async def process_feedback_text(message: Message, state: FSMContext):
    lang = await _get_user_lang(message.from_user.id)
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ أرسل نصاً أو صورة/PDF." if lang == "ar" else "❌ Send text or an image/PDF.", reply_markup=cancel_keyboard(lang))
        return
    if len(text) > MAX_TEXT_LENGTH:
        await message.answer(locale_service.get("feedback_too_long", lang, length=len(text)), reply_markup=cancel_keyboard(lang))
        return

    user = await _store_feedback(message, text, None, None)
    if not user:
        await message.answer("يرجى البدء أولاً: /start")
        await state.clear()
        return
    try:
        await _notify_feedback(user, text, None, None)
    except Exception:
        logger.exception("Failed to notify admins about feedback")
    await message.answer(locale_service.get("feedback_sent", lang), reply_markup=compact_reply_keyboard(lang))
    await state.clear()


@router.message(FeedbackStates.waiting_message, F.photo)
async def process_feedback_photo(message: Message, state: FSMContext):
    lang = await _get_user_lang(message.from_user.id)
    caption = (message.caption or "").strip()
    if len(caption) > MAX_TEXT_LENGTH:
        await message.answer(locale_service.get("feedback_too_long", lang, length=len(caption)), reply_markup=cancel_keyboard(lang))
        return

    buffer = BytesIO()
    try:
        await message.bot.download(file=message.photo[-1].file_id, destination=buffer)
        validate_image_payload(buffer.getvalue(), mime_type="image/jpeg", file_name="feedback.jpg")
    except ValueError:
        await message.answer("❌ نوع أو حجم الصورة غير مسموح." if lang == "ar" else "❌ This image type or size is not allowed.", reply_markup=cancel_keyboard(lang))
        return
    except Exception:
        logger.exception("Failed to validate feedback photo")
        await message.answer("❌ تعذر فحص الصورة." if lang == "ar" else "❌ The image could not be validated.", reply_markup=cancel_keyboard(lang))
        return

    user = await _store_feedback(message, caption, "photo", message.photo[-1].file_id)
    if not user:
        await message.answer("يرجى البدء أولاً: /start")
        await state.clear()
        return
    try:
        await _notify_feedback(user, caption, "photo", message.photo[-1].file_id)
    except Exception:
        logger.exception("Failed to notify admins about feedback photo")
    await message.answer(locale_service.get("feedback_sent", lang), reply_markup=compact_reply_keyboard(lang))
    await state.clear()


@router.message(FeedbackStates.waiting_message, F.document)
async def process_feedback_document(message: Message, state: FSMContext):
    lang = await _get_user_lang(message.from_user.id)
    caption = (message.caption or "").strip()
    if len(caption) > MAX_TEXT_LENGTH:
        await message.answer(locale_service.get("feedback_too_long", lang, length=len(caption)), reply_markup=cancel_keyboard(lang))
        return

    if (message.document.mime_type or "").lower() != "application/pdf":
        await message.answer("❌ الدعم يقبل الصور وPDF فقط." if lang == "ar" else "❌ Support accepts images and PDF only.", reply_markup=cancel_keyboard(lang))
        return

    buffer = BytesIO()
    try:
        await message.bot.download(file=message.document.file_id, destination=buffer)
        validate_pdf_payload(buffer.getvalue(), mime_type=message.document.mime_type, file_name=message.document.file_name)
    except ValueError:
        await message.answer("❌ ملف PDF غير صالح أو يتجاوز الحدود المسموحة." if lang == "ar" else "❌ This PDF is invalid or exceeds the allowed limits.", reply_markup=cancel_keyboard(lang))
        return
    except Exception:
        logger.exception("Failed to validate feedback PDF")
        await message.answer("❌ تعذر فحص ملف PDF." if lang == "ar" else "❌ The PDF could not be validated.", reply_markup=cancel_keyboard(lang))
        return

    user = await _store_feedback(message, caption, "pdf", message.document.file_id)
    if not user:
        await message.answer("يرجى البدء أولاً: /start")
        await state.clear()
        return
    try:
        await _notify_feedback(user, caption, "pdf", message.document.file_id)
    except Exception:
        logger.exception("Failed to notify admins about feedback PDF")
    await message.answer(locale_service.get("feedback_sent", lang), reply_markup=compact_reply_keyboard(lang))
    await state.clear()


@router.message(FeedbackStates.waiting_message)
async def reject_unsupported_feedback_input(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    await message.answer("❌ الدعم يقبل نصاً حتى 200 حرف، أو صورة، أو PDF فقط." if lang == "ar" else "❌ Support accepts up to 200 characters of text, an image, or PDF only.", reply_markup=cancel_keyboard(lang))
