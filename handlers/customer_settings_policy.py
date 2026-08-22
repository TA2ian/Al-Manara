"""Authoritative customer settings/quick-actions entry point."""
from aiogram import F, Router
from aiogram.types import Message

from config import Config
from database import get_pool
from keyboards.inline import quick_actions_keyboard, main_menu_inline
from services.locale_service import locale_service

router = Router()


@router.message(F.text.in_({"⚙️ القائمة", "⚙️ Menu", "⚙️ الإعدادات", "⚙️ Settings"}))
async def customer_settings(message: Message):
    """Open the customer quick-actions panel from the persistent reply keyboard."""
    pool = await get_pool()
    user = None
    if pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT language, is_blocked FROM users WHERE telegram_id = $1",
                message.from_user.id,
            )

    if not user:
        await message.answer("يرجى بدء البوت أولاً: /start")
        return

    lang = user["language"] or "ar"
    if user["is_blocked"]:
        await message.answer(locale_service.get("user_blocked", lang), parse_mode="HTML")
        return

    title = "⚙️ <b>الإعدادات والإجراءات السريعة</b>" if lang == "ar" else "⚙️ <b>Settings & Quick Actions</b>"
    await message.answer(
        title,
        reply_markup=quick_actions_keyboard(lang),
        parse_mode="HTML",
    )
