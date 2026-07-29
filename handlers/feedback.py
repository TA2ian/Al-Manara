"""Feedback handlers."""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import FeedbackStates
from keyboards.inline import cancel_keyboard, main_menu_inline
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from services.notification_service import NotificationService
from database import get_pool
from config import Config

logger = logging.getLogger(__name__)
router = Router()


async def _get_user_lang(telegram_id: int) -> str:
    """Fetch user language from DB."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
            if user:
                return user['language']
    except Exception:
        pass
    return 'ar'


@router.callback_query(F.data == "menu_feedback")
async def start_feedback(callback: CallbackQuery, state: FSMContext):
    """Start feedback process."""
    lang = await _get_user_lang(callback.from_user.id)

    await callback.message.edit_text(
        locale_service.get('feedback_prompt', lang),
        reply_markup=cancel_keyboard(lang)
    )

    await state.set_state(FeedbackStates.waiting_message)
    await callback.answer()


@router.message(FeedbackStates.waiting_message)
async def process_feedback(message: Message, state: FSMContext):
    """Process feedback message."""
    lang = await _get_user_lang(message.from_user.id)

    if len(message.text) > 200:
        await message.answer(
            locale_service.get('feedback_too_long', lang, length=len(message.text)),
            reply_markup=cancel_keyboard(lang)
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

        if not user:
            await message.answer("يرجى البدء أولاً: /start")
            await state.clear()
            return

        await conn.execute(
            "INSERT INTO feedback_messages (user_id, message) VALUES ($1, $2)",
            user['id'], message.text
        )

    # Notify admins (outside pool context)
    bot = Bot(token=Config.BOT_TOKEN)
    notification = NotificationService(bot, Config.ADMIN_IDS)
    await notification.notify_feedback(dict(user), message.text)

    await message.answer(
        locale_service.get('feedback_sent', lang),
        reply_markup=compact_reply_keyboard(lang)
    )

    await state.clear()
