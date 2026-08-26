"""Middleware enforcing administrative customer-service suspensions."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import Config
from database import get_pool
from services.user_misconduct_service import get_suspension, suspension_notice


class UserSuspensionMiddleware(BaseMiddleware):
    """Stop suspended customers before customer handlers execute."""

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None or user.id in Config.ADMIN_IDS:
            return await handler(event, data)

        pool = await get_pool()
        if pool is None:
            return await handler(event, data)

        try:
            async with pool.acquire() as conn:
                suspension = await get_suspension(conn, user.id)
        except Exception:
            return await handler(event, data)

        if not suspension:
            return await handler(event, data)

        if not suspension["is_blocked"] and not suspension["expires_at"]:
            return await handler(event, data)

        if suspension["is_blocked"] or suspension["expires_at"]:
            lang = "ar"
            try:
                async with pool.acquire() as conn:
                    stored_lang = await conn.fetchval(
                        "SELECT language FROM users WHERE telegram_id = $1",
                        user.id,
                    )
                if stored_lang in ("ar", "en"):
                    lang = stored_lang
            except Exception:
                pass

            notice = suspension_notice(
                suspension["reason"],
                suspension["expires_at"],
                lang,
            )
            if isinstance(event, Message):
                await event.answer(notice, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer(notice, show_alert=True)
            return

        return await handler(event, data)
