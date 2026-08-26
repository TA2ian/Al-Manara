from datetime import datetime, timedelta, timezone

from services.receipt_retry_policy import (
    MAX_RECEIPT_ATTEMPTS,
    RECEIPT_RETRY_EXTENSION_MINUTES,
    expired_retry_extension,
)


def test_expired_deadline_gets_exact_five_minute_extension_when_attempts_remain():
    now = datetime.now(timezone.utc)
    deadline = now - timedelta(seconds=1)

    extended = expired_retry_extension(deadline, 1, now=now)

    assert extended == now + timedelta(minutes=RECEIPT_RETRY_EXTENSION_MINUTES)


def test_unexpired_deadline_is_not_extended():
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(minutes=2)

    assert expired_retry_extension(deadline, 1, now=now) is None


def test_exhausted_attempts_are_not_extended():
    now = datetime.now(timezone.utc)
    deadline = now - timedelta(minutes=2)

    assert expired_retry_extension(deadline, MAX_RECEIPT_ATTEMPTS, now=now) is None


def test_missing_deadline_is_not_extended():
    assert expired_retry_extension(None, 1) is None
