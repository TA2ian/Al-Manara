"""Durable ownership for the manual USDT fulfillment step."""
from __future__ import annotations

from database import get_pool


async def init_fulfillment_claims() -> None:
    """Create the fulfillment-claim table used to serialize manual transfers."""
    pool = await get_pool()
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_fulfillment_claims (
                order_id INTEGER PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
                admin_id BIGINT NOT NULL,
                claimed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                released_at TIMESTAMP,
                completed_at TIMESTAMP,
                txid TEXT,
                screenshot_id TEXT
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fulfillment_claims_admin_active "
            "ON order_fulfillment_claims (admin_id) WHERE completed_at IS NULL AND released_at IS NULL"
        )
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_fulfillment_completed_txid "
            "ON order_fulfillment_claims (txid) WHERE txid IS NOT NULL"
        )


async def claim_order_fulfillment(order_id: int, admin_id: int) -> str:
    """Claim an eligible order for one admin; return ownership state."""
    pool = await get_pool()
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                "SELECT status FROM orders WHERE id = $1 FOR UPDATE",
                order_id,
            )
            if not order:
                return "missing_order"
            if order["status"] != "payment_confirmed":
                return "invalid_order_state"

            claim = await conn.fetchrow(
                "SELECT admin_id, released_at, completed_at FROM order_fulfillment_claims WHERE order_id = $1 FOR UPDATE",
                order_id,
            )
            if claim:
                if claim["completed_at"] is not None:
                    return "completed"
                if claim["released_at"] is None:
                    return "owned_by_current_admin" if int(claim["admin_id"]) == int(admin_id) else "owned_by_other_admin"
                await conn.execute(
                    """
                    UPDATE order_fulfillment_claims
                    SET admin_id = $2, claimed_at = NOW(), released_at = NULL, txid = NULL, screenshot_id = NULL
                    WHERE order_id = $1
                    """,
                    order_id,
                    admin_id,
                )
                return "claimed"

            await conn.execute(
                "INSERT INTO order_fulfillment_claims (order_id, admin_id) VALUES ($1, $2)",
                order_id,
                admin_id,
            )
            return "claimed"


async def release_order_fulfillment(order_id: int, admin_id: int) -> bool:
    """Release a claim owned by the requesting admin without changing order state."""
    pool = await get_pool()
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE order_fulfillment_claims
            SET released_at = NOW()
            WHERE order_id = $1 AND admin_id = $2 AND released_at IS NULL AND completed_at IS NULL
            """,
            order_id,
            admin_id,
        )
    return result == "UPDATE 1"
