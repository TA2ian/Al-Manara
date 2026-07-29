"""Feedback handlers."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import FeedbackStates
from keyboards.inline import cancel_keyboard, main_menu_inline
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from services.notification_service import NotificationService
from database import get_pool
from config import Config

router = Router()


@router.callback_query(F.data == "menu_feedback")
async def start_feedback(callback: CallbackQuery, state: FSMContext):
    """Start feedback process."""
    lang = 'ar'  # Get from user

    await callback.message.edit_text(
        locale_service.get('feedback_prompt', lang),
        reply_markup=cancel_keyboard(lang)
    )

    await state.set_state(FeedbackStates.waiting_message)
    await callback.answer()


@router.message(FeedbackStates.waiting_message)
async def process_feedback(message: Message, state: FSMContext):
    """Process feedback message."""
    lang = 'ar'  # Get from user

    if len(message.text) > 200:
        await message.answer(
            locale_service.get('feedback_too_long', lang, length=len(message.text)),
            reply_markup=cancel_keyboard(lang)
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

        await conn.execute(
            "INSERT INTO feedback_messages (user_id, message) VALUES ($1, $2)",
            user['id'], message.text
        )

    # Notify admins
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    notification = NotificationService(bot, Config.ADMIN_IDS)

    user_data = await conn.fetchrow(
        "SELECT * FROM users WHERE telegram_id = $1", message.from_user.id
    )

    await notification.notify_feedback(dict(user_data), message.text)

    await message.answer(
        locale_service.get('feedback_sent', lang),
        reply_markup=compact_reply_keyboard(lang)
    )

    await state.clear()
