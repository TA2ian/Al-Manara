"""Authoritative policy for expired payment deadlines after receipt rejection."""
from __future__ import annotations

from datetime import datetime, timedelta


RECEIPT_RETRY_EXTENSION_MINUTES = 5
MAX_RECEIPT_ATTEMPTS = 3


def expired_retry_extension(
    payment_deadline: datetime | None,
    receipt_upload_count: int | None,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """Return a five-minute retry deadline only when the old deadline expired and attempts remain."""
    if payment_deadline is None:
        return None

    attempts_used = max(0, int(receipt_upload_count or 0))
    remaining_attempts = MAX_RECEIPT_ATTEMPTS - attempts_used
    if remaining_attempts <= 0:
        return None

    current_time = now or datetime.now(payment_deadline.tzinfo)
    if payment_deadline > current_time:
        return None

    return current_time + timedelta(minutes=RECEIPT_RETRY_EXTENSION_MINUTES)
