"""Persistent single-admin claim for the external USDT fulfillment step."""
from __future__ import annotations

from typing import Any


CLAIM_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS order_fulfillment_claims (
    order_id INTEGER PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
    admin_id BIGINT NOT NULL,
    claimed_at TIMESTAMP NOT NULL DEFAULT NOW()
)
"""


async def ensure_fulfillment_claim_table(conn) -> None:
    """Create the persistent fulfillment-claim table when it is first needed."""
    await conn.execute(CLAIM_TABLE_SQL)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_order_fulfillment_claims_admin "
        "ON order_fulfillment_claims (admin_id)"
    )


async def get_fulfillment_claim(conn, order_id: int):
    """Return the current fulfillment claim for an order, if any."""
    await ensure_fulfillment_claim_table(conn)
    return await conn.fetchrow(
        "SELECT order_id, admin_id, claimed_at "
        "FROM order_fulfillment_claims WHERE order_id = $1",
        order_id,
    )


async def claim_order_fulfillment(conn, order_id: int, admin_id: int) -> tuple[bool, Any]:
    """Atomically claim an eligible payment-confirmed order for one admin."""
    await ensure_fulfillment_claim_table(conn)
    async with conn.transaction():
        order = await conn.fetchrow(
            "SELECT id, status FROM orders WHERE id = $1 FOR UPDATE",
            order_id,
        )
        if not order:
            return False, None
        if order["status"] != "payment_confirmed":
            return False, None

        claim = await conn.fetchrow(
            "SELECT order_id, admin_id, claimed_at "
            "FROM order_fulfillment_claims WHERE order_id = $1 FOR UPDATE",
            order_id,
        )
        if claim:
            return int(claim["admin_id"]) == int(admin_id), claim

        claim = await conn.fetchrow(
            """INSERT INTO order_fulfillment_claims (order_id, admin_id)
               VALUES ($1, $2)
               RETURNING order_id, admin_id, claimed_at""",
            order_id,
            admin_id,
        )
        await conn.execute(
            """INSERT INTO audit_logs
               (user_id, admin_id, action, details, previous_value, new_value, severity)
               SELECT user_id, $2, 'fulfillment_claim_acquired', $3, NULL, $4, 'info'
               FROM orders WHERE id = $1""",
            order_id,
            admin_id,
            f"order_id={order_id}",
            f"admin_id={admin_id}",
        )
        return True, claim


async def release_order_fulfillment(conn, order_id: int, admin_id: int) -> bool:
    """Release a fulfillment claim only when it belongs to the requesting admin."""
    await ensure_fulfillment_claim_table(conn)
    async with conn.transaction():
        order = await conn.fetchrow(
            "SELECT id, user_id FROM orders WHERE id = $1 FOR UPDATE",
            order_id,
        )
        if not order:
            return False

        deleted = await conn.fetchrow(
            """DELETE FROM order_fulfillment_claims
               WHERE order_id = $1 AND admin_id = $2
               RETURNING order_id""",
            order_id,
            admin_id,
        )
        if not deleted:
            return False

        await conn.execute(
            """INSERT INTO audit_logs
               (user_id, admin_id, action, details, previous_value, new_value, severity)
               VALUES ($1, $2, 'fulfillment_claim_released', $3, $4, NULL, 'info')""",
            order["user_id"],
            admin_id,
            f"order_id={order_id}",
            f"admin_id={admin_id}",
        )
        return True


async def release_claim_after_completion(conn, order_id: int, admin_id: int) -> None:
    """Delete a successful fulfillment claim inside the caller-owned transaction."""
    await ensure_fulfillment_claim_table(conn)
    await conn.execute(
        "DELETE FROM order_fulfillment_claims WHERE order_id = $1 AND admin_id = $2",
        order_id,
        admin_id,
    )
