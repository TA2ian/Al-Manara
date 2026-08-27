"""Maintenance middleware using the database-backed maintenance policy."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import Config
from services.maintenance_service import MaintenanceMode, MaintenanceService
from states import ReceiptStates


class MaintenanceMiddleware(BaseMiddleware):
    """Block customer operations while keeping the complete admin surface available."""

    async def _is_receipt_submission(self, event, data) -> bool:
        state = data.get("state")
        if isinstance(event, Message) and state is not None:
            try:
                return await state.get_state() == ReceiptStates.waiting_receipt.state
            except Exception:
                return False
        if isinstance(event, CallbackQuery):
            return (event.data or "").startswith("upload_receipt_")
        return False

    async def __call__(self, handler, event, data):
        mode = await MaintenanceService.get_mode()
        if mode in (MaintenanceMode.OFF, MaintenanceMode.LIMITED):
            return await handler(event, data)

        user_id = event.from_user.id if isinstance(event, (Message, CallbackQuery)) else None

        # Administration is an explicit privileged surface and must remain
        # reachable in every maintenance mode, including EMERGENCY. All actual
        # admin handlers still perform their own authorization checks.
        if Config.is_admin(user_id):
            return await handler(event, data)

        if mode == MaintenanceMode.MAINTENANCE and await self._is_receipt_submission(event, data):
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
