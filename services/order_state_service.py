"""Atomic order state transitions with audit logging."""
from __future__ import annotations

from typing import Any


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"waiting_payment", "rejected", "expired"}),
    "waiting_payment": frozenset({"receipt_received", "expired"}),
    "receipt_received": frozenset({"waiting_payment", "payment_confirmed"}),
    "payment_confirmed": frozenset({"completed"}),
    "completed": frozenset(),
    "rejected": frozenset(),
    "expired": frozenset(),
}


class InvalidOrderTransition(ValueError):
    """Raised when an order state transition is not allowed."""


async def transition_order(
    conn,
    order_id: int,
    target_status: str,
    *,
    admin_id: int | None = None,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically lock an order, validate its transition, update it, and audit it."""
    if target_status not in ALLOWED_TRANSITIONS:
        raise InvalidOrderTransition(f"Unknown target status: {target_status}")

    order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1 FOR UPDATE", order_id)
    if not order:
        raise InvalidOrderTransition("Order not found")

    current = order["status"]
    if current == target_status:
        raise InvalidOrderTransition(f"Order is already {target_status}")

    if target_status not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidOrderTransition(f"Invalid transition: {current} -> {target_status}")

    fields = ["status = $1"]
    values: list[Any] = [target_status]
    param = 2
    for key, value in (updates or {}).items():
        if key not in {
            "approved_at",
            "payment_deadline",
            "completed_at",
            "txid",
            "admin_notes",
            "receipt_photo_id",
            "receipt_upload_count",
            "wallet_qr_photo_id",
        }:
            raise ValueError(f"Unsupported order update field: {key}")
        fields.append(f"{key} = ${param}")
        values.append(value)
        param += 1

    values.append(order_id)
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
        "order_status_transition",
        f"order_id={order_id}",
        current,
        target_status,
        "info",
    )

    return await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
