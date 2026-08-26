"""Authoritative order lifecycle classification used by customer gates."""

ACTIVE_ORDER_STATUSES = frozenset(
    {
        "pending",
        "waiting_payment",
        "receipt_received",
        "payment_confirmed",
    }
)

TERMINAL_ORDER_STATUSES = frozenset({"completed", "rejected", "expired"})


def is_active_order_status(status: str | None) -> bool:
    """Return whether an order must continue blocking creation of another order."""
    return status in ACTIVE_ORDER_STATUSES


def is_terminal_order_status(status: str | None) -> bool:
    """Return whether an order no longer blocks creation of another order."""
    return status in TERMINAL_ORDER_STATUSES
