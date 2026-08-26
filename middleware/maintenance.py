"""Maintenance middleware using the database-backed maintenance policy."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import Config
from services.locale_service import locale_service
from services.maintenance_service import MaintenanceService, MaintenanceMode


class MaintenanceMiddleware(BaseMiddleware):
    """Block only flows that the active maintenance mode actually disables."""

    async def __call__(self, handler, event, data):
        mode = await MaintenanceService.get_mode()
        if mode == MaintenanceMode.OFF:
            return await handler(event, data)

        user_id = event.from_user.id if isinstance(event, (Message, CallbackQuery)) else None
        if user_id in Config.ADMIN_IDS:
            return await handler(event, data)

        lang = "ar"
        if isinstance(event, (Message, CallbackQuery)):
            lang = event.from_user.language_code or "ar"
            if lang not in ("ar", "en"):
                lang = "ar"

        if mode == MaintenanceMode.LIMITED:
            return await handler(event, data)

        key = MaintenanceService.user_message_key(mode)
        if isinstance(event, Message):
            await event.answer(locale_service.get(key, lang))
        elif isinstance(event, CallbackQuery):
            await event.answer(locale_service.get(key, lang), show_alert=True)
        return
