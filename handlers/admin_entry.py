"""Admin entry point from the regular settings button."""
from aiogram import Router, F
from aiogram.types import Message

from config import Config
from database import get_pool
from handlers.payment_methods import enhanced_admin_menu_keyboard

router = Router()


@router.message(F.text.func(lambda text: isinstance(text, str) and "⚙" in text))
async def open_admin_from_settings(message: Message):
    """Open the admin panel directly for configured administrators."""
    if message.from_user.id not in Config.ADMIN_IDS:
        return

    pool = await get_pool()
    lang = "ar"
    if pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT language FROM users WHERE telegram_id = $1",
                message.from_user.id,
            )
            if user and user["language"]:
                lang = user["language"]

    if lang == "ar":
        text = (
            "👨‍💼 <b>لوحة الإدارة</b>\n\n"
            "اختر العملية المطلوبة من القائمة أدناه.\n"
            "يمكنك الوصول إليها من زر ⚙️ دون الحاجة إلى كتابة /admin."
        )
    else:
        text = (
            "👨‍💼 <b>Admin Panel</b>\n\n"
            "Choose an action below.\n"
            "You can now open the panel from ⚙️ without typing /admin."
        )

    await message.answer(text, reply_markup=enhanced_admin_menu_keyboard(), parse_mode="HTML")
