"""Rate limiting middleware."""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from services.rate_limiter import RateLimiter
from services.locale_service import locale_service

rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware - skipped for admins."""

    async def __call__(self, handler, event, data):
        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            # Skip rate limiting for admins
            from config import Config
            if user_id in Config.ADMIN_IDS:
                return await handler(event, data)

            allowed, wait = rate_limiter.check(user_id)

            if not allowed:
                lang = data.get('user', {}).get('language', 'ar') if 'user' in data else 'ar'

                if isinstance(event, Message):
                    await event.answer(
                        locale_service.get('rate_limit_exceeded', lang, seconds=wait)
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        locale_service.get('rate_limit_exceeded', lang, seconds=wait),
                        show_alert=True
                    )
                return

        return await handler(event, data)
