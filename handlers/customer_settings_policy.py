"""Authoritative customer settings/quick-actions entry point."""
import unicodedata

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import get_pool
from keyboards.inline import quick_actions_keyboard
from services.locale_service import locale_service

router = Router()


_SUPPORTED_MENU_LABELS = frozenset(
    {
        "⚙️ القائمة",
        "القائمة ⚙️",
        "القائمة",
        "⚙️ Menu",
        "Menu ⚙️",
        "Menu",
        "⚙️ الإعدادات",
        "الإعدادات ⚙️",
        "الإعدادات",
        "⚙️ Settings",
        "Settings ⚙️",
        "Settings",
    }
)


def _normalize_menu_label(value: str | None) -> str:
    """Normalize Telegram reply-button text without accepting arbitrary input."""
    if not value:
        return ""
    normalized = "".join(
        character for character in unicodedata.normalize("NFKC", value)
        if unicodedata.category(character) != "Cf"
    )
    return " ".join(normalized.split()).strip()


@router.message(F.text.func(lambda text: _normalize_menu_label(text) in _SUPPORTED_MENU_LABELS))
async def customer_settings(message: Message, state: FSMContext):
    """Open the customer quick-actions panel and clear any stale customer FSM step."""
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

    await state.clear()
    title = "⚙️ <b>الإعدادات والإجراءات السريعة</b>" if lang == "ar" else "⚙️ <b>Settings & Quick Actions</b>"
    await message.answer(
        title,
        reply_markup=quick_actions_keyboard(lang),
        parse_mode="HTML",
    )
