"""Database-backed serialization for receipt processing per order."""
from __future__ import annotations

from contextlib import asynccontextmanager

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
