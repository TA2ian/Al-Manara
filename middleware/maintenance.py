"""Maintenance middleware using the database-backed maintenance policy."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import Config
from services.maintenance_service import MaintenanceMode, MaintenanceService


class MaintenanceMiddleware(BaseMiddleware):
    """Block only operations that the active maintenance mode actually disables."""

    async def __call__(self, handler, event, data):
        mode = await MaintenanceService.get_mode()
        if mode in (MaintenanceMode.OFF, MaintenanceMode.LIMITED):
            return await handler(event, data)

        user_id = event.from_user.id if isinstance(event, (Message, CallbackQuery)) else None
        if user_id in Config.ADMIN_IDS:
            return await handler(event, data)

        lang = "ar"
        if isinstance(event, (Message, CallbackQuery)):
            lang = event.from_user.language_code or "ar"
            if lang not in ("ar", "en"):
                lang = "ar"

        notice = MaintenanceService.user_notice(mode, lang)
        if isinstance(event, Message):
            await event.answer(notice, parse_mode="HTML")
        elif isinstance(event, CallbackQuery):
            await event.answer(notice, show_alert=True)
        return
