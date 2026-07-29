"""Maintenance mode middleware."""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from config import Config
from services.locale_service import locale_service


class MaintenanceMiddleware(BaseMiddleware):
    """Block users during maintenance."""

    async def __call__(self, handler, event, data):
        if not Config.MAINTENANCE_MODE:
            return await handler(event, data)

        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        # Allow admins during maintenance
        if user_id in Config.ADMIN_IDS:
            return await handler(event, data)

        lang = 'ar'
        if isinstance(event, (Message, CallbackQuery)):
            lang = event.from_user.language_code or 'ar'
            if lang not in ['ar', 'en']:
                lang = 'ar'

        if isinstance(event, Message):
            await event.answer(locale_service.get('maintenance_mode', lang))
        elif isinstance(event, CallbackQuery):
            await event.answer(locale_service.get('maintenance_mode', lang), show_alert=True)

        return
