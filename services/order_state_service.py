"""Atomic order state transitions with audit logging."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"waiting_payment", "rejected", "expired"}),
    "waiting_payment": frozenset({"receipt_received", "rejected", "expired"}),
    "receipt_received": frozenset({"waiting_payment", "payment_confirmed", "rejected"}),
    "payment_confirmed": frozenset({"completed"}),
    "completed": frozenset(),
    "rejected": frozenset(),
    "expired": frozenset(),
}


ALLOWED_ORDER_UPDATE_FIELDS = frozenset(
    {
        "approved_at",
        "payment_deadline",
        "completed_at",
        "txid",
        "admin_notes",
        "receipt_photo_id",
        "receipt_upload_count",
        "wallet_qr_photo_id",
    }
)


class InvalidOrderTransition(ValueError):
    """Raised when an order state transition is not allowed."""


@asynccontextmanager
async def _transaction_scope(conn):
    """Use the caller transaction when one already owns the connection."""
    if conn.is_in_transaction():
        yield
        return
    async with conn.transaction():
        yield


async def transition_order(
    conn,
    order_id: int,
    target_status: str,
    *,
    admin_id: int | None = None,
    updates: dict[str, Any] | None = None,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically lock an order, validate guards and transition it with audit logging."""
    if target_status not in ALLOWED_TRANSITIONS:
        raise InvalidOrderTransition(f"Unknown target status: {target_status}")

    async with _transaction_scope(conn):
        order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1 FOR UPDATE", order_id)
        if not order:
            raise InvalidOrderTransition("Order not found")

        current = order["status"]
        if current == target_status:
            raise InvalidOrderTransition(f"Order is already {target_status}")

        if target_status not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise InvalidOrderTransition(f"Invalid transition: {current} -> {target_status}")

        for field, expected_value in (expected or {}).items():
            if field not in order:
                raise ValueError(f"Unsupported order guard field: {field}")
            actual_value = order[field]
            if field in {"network", "wallet_address"}:
                actual = (actual_value or "").strip().lower()
                expected_normalized = (expected_value or "").strip().lower()
                if actual != expected_normalized:
                    raise InvalidOrderTransition(f"Order guard mismatch: {field}")
            elif actual_value != expected_value:
                raise InvalidOrderTransition(f"Order guard mismatch: {field}")

        return await _apply_status_update(
            conn,
            order,
            target_status,
            admin_id=admin_id,
            updates=updates,
            action="order_status_transition",
        )


async def rollback_order(
    conn,
    order_id: int,
    target_status: str,
    *,
    admin_id: int | None = None,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Perform a narrowly-scoped compensating rollback and audit it.

    This is intentionally separate from the business transition graph. It is
    used when an external delivery operation fails after a state was advanced.
    Currently only waiting_payment -> pending is supported.
    """
    if target_status != "pending":
        raise InvalidOrderTransition("Unsupported rollback target")

    async with _transaction_scope(conn):
        order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1 FOR UPDATE", order_id)
        if not order:
            raise InvalidOrderTransition("Order not found")
        if order["status"] != "waiting_payment":
            raise InvalidOrderTransition(f"Invalid rollback from {order['status']}")

        return await _apply_status_update(
            conn,
            order,
            target_status,
            admin_id=admin_id,
            updates=updates,
            action="order_status_rollback",
        )


async def _apply_status_update(
    conn,
    order,
    target_status: str,
    *,
    admin_id: int | None,
    updates: dict[str, Any] | None,
    action: str,
) -> dict[str, Any]:
    fields = ["status = $1"]
    values: list[Any] = [target_status]
    param = 2
    for key, value in (updates or {}).items():
        if key not in ALLOWED_ORDER_UPDATE_FIELDS:
            raise ValueError(f"Unsupported order update field: {key}")
        fields.append(f"{key} = ${param}")
        values.append(value)
        param += 1

    values.append(order["id"])
    await conn.execute(
        f"UPDATE orders SET {', '.join(fields)} WHERE id = ${param}",
        *values,
    )
    await conn.execute(
        """INSERT INTO audit_logs
           (user_id, admin_id, action, details, previous_value, new_value, severity)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        order["user_id"],
        admin_id,
        action,
        f"order_id={order['id']}",
        order["status"],
        target_status,
        "info",
    )
    return await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order["id"])
