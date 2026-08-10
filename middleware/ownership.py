"""Callback ownership guard for user-facing order and wallet actions."""
import re

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool


ORDER_ID_PATTERNS = (
    re.compile(r"^(?:upload_receipt|retry_receipt|manual_review|rate)_([0-9]+)$"),
)
WALLET_ID_PATTERNS = (
    re.compile(r"^(?:view_addr|del_addr|set_default_addr)_([0-9]+)$"),
)


class OwnershipMiddleware(BaseMiddleware):
    """Reject user callbacks that reference another user's order or wallet."""

    async def __call__(self, handler, event, data):
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        callback_data = event.data or ""
        if event.from_user.id in Config.ADMIN_IDS:
            return await handler(event, data)

        resource_type = None
        resource_id = None
        for pattern in ORDER_ID_PATTERNS:
            match = pattern.match(callback_data)
            if match:
                resource_type, resource_id = "order", int(match.group(1))
                break
        if resource_id is None:
            for pattern in WALLET_ID_PATTERNS:
                match = pattern.match(callback_data)
                if match:
                    resource_type, resource_id = "wallet", int(match.group(1))
                    break

        if resource_id is None:
            return await handler(event, data)

        pool = await get_pool()
        if not pool:
            await event.answer("❌ الخدمة غير متاحة حالياً", show_alert=True)
            return

        async with pool.acquire() as conn:
            if resource_type == "order":
                owner = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1
                        FROM orders o
                        JOIN users u ON u.id = o.user_id
                        WHERE o.id = $1 AND u.telegram_id = $2
                    )
                    """,
                    resource_id,
                    event.from_user.id,
                )
            else:
                owner = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1
                        FROM saved_addresses a
                        JOIN users u ON u.id = a.user_id
                        WHERE a.id = $1 AND u.telegram_id = $2
                    )
                    """,
                    resource_id,
                    event.from_user.id,
                )

        if not owner:
            await event.answer("⛔ لا تملك صلاحية الوصول لهذا السجل", show_alert=True)
            return

        return await handler(event, data)
