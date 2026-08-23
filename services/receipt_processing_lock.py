"""Database-backed serialization for receipt processing per order."""
from __future__ import annotations

from contextlib import asynccontextmanager
from functools import wraps

from database import get_pool


@asynccontextmanager
async def receipt_processing_lock(order_id: int):
    """Yield True only to the single worker processing an order receipt."""
    pool = await get_pool()
    connection = await pool.acquire()
    locked = False
    try:
        locked = bool(
            await connection.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1, 0))",
                f"al-manara:receipt:{int(order_id)}",
            )
        )
        yield locked
    finally:
        if locked:
            await connection.execute(
                "SELECT pg_advisory_unlock(hashtextextended($1, 0))",
                f"al-manara:receipt:{int(order_id)}",
            )
        await pool.release(connection)


def serialize_receipt_handler(handler):
    """Serialize a Telegram receipt handler by the order id stored in FSM data."""
    @wraps(handler)
    async def wrapped(message, state, *args, **kwargs):
        data = await state.get_data()
        order_id = data.get("receipt_order_id")
        if not order_id:
            return await handler(message, state, *args, **kwargs)
        async with receipt_processing_lock(int(order_id)) as acquired:
            if not acquired:
                await message.answer("⏳ جارٍ التحقق من إيصال آخر لهذا الطلب. انتظر النتيجة قبل إرسال إثبات آخر.")
                return
            return await handler(message, state, *args, **kwargs)
    return wrapped
