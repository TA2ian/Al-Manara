"""Profile handlers."""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from keyboards.inline import main_menu_inline
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from database import get_pool

router = Router()


@router.callback_query(F.data == "menu_profile")
async def show_profile(callback: CallbackQuery):
    """Show user profile."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            callback.from_user.id
        )

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    status = locale_service.get('verified' if user['is_verified'] else 'not_verified', user['language'])

    text = locale_service.get(
        'profile_info',
        user['language'],
        telegram_id=user['telegram_id'],
        full_name=user['full_name'] or 'N/A',
        status=status,
        language=locale_service.get_language_name(user['language']),
        created_at=user['created_at'].strftime('%Y-%m-%d') if user['created_at'] else 'N/A'
    )

    await callback.message.edit_text(text, parse_mode='HTML')
    await callback.message.answer(
        locale_service.get('main_menu', user['language']),
        reply_markup=main_menu_inline(user['language'])
    )
    await callback.answer()
