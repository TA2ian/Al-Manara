"""Admin-only reply-keyboard shortcut for the dashboard."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from handlers.admin_entry import _send_admin_menu

router = Router()


@router.message(F.text.in_({"👑 لوحة الأدمن", "👑 Admin Dashboard"}))
async def open_admin_dashboard_shortcut(message: Message, state: FSMContext):
    """Open the admin dashboard only for configured administrators."""
    if message.from_user.id not in Config.ADMIN_IDS:
        return
    await state.clear()
    await _send_admin_menu(message)
