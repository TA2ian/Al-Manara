"""Database-backed serialization for expensive or state-sensitive user input."""
from __future__ import annotations

from contextlib import asynccontextmanager

from aiogram import BaseMiddleware
from aiogram.types import Message

from database import get_pool


SENSITIVE_STATES = frozenset(
    {
        "VerificationStates:waiting_shamcash_identity",
        "WalletStates:waiting_address",
        "WalletStates:waiting_qr",
        "ReceiptStates:waiting_receipt",
        "FeedbackStates:waiting_message",
    }
)


@asynccontextmanager
async def state_processing_lock(user_id: int, state_name: str):
    """Hold a PostgreSQL session advisory lock for one sensitive FSM state."""
    pool = await get_pool()
    if pool is None:
        raise RuntimeError("database pool is not initialized")

    connection = await pool.acquire()
    locked = False
    key = f"al-manara:state-processing:{int(user_id)}:{state_name}"
    try:
        locked = bool(
            await connection.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1, 0))",
                key,
            )
        )
        yield locked
    finally:
        if locked:
            await connection.execute(
                "SELECT pg_advisory_unlock(hashtextextended($1, 0))",
                key,
            )
        await pool.release(connection)


class StateProcessingLockMiddleware(BaseMiddleware):
    """Prevent duplicate concurrent submissions for sensitive customer states."""

    async def __call__(self, handler, event, data):
        if not isinstance(event, Message):
            return await handler(event, data)

        user = event.from_user
        if user is None:
            return await handler(event, data)

        state = data.get("state")
        if state is None:
            return await handler(event, data)

        state_name = await state.get_state()
        if state_name not in SENSITIVE_STATES:
            return await handler(event, data)

        async with state_processing_lock(user.id, state_name) as acquired:
            if acquired:
                return await handler(event, data)

            await event.answer(
                "⏳ تتم معالجة إدخال سابق الآن. انتظر النتيجة قبل إرسال محاولة أخرى."
                if (user.language_code or "ar").startswith("ar")
                else
                "⏳ A previous submission is being processed. Wait for the result before sending another attempt."
            )
            return
