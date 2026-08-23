"""Regression tests for sensitive callback ownership patterns."""

from middleware.ownership import ORDER_ID_PATTERNS, WALLET_ID_PATTERNS


def _matches(patterns, callback_data: str) -> bool:
    return any(pattern.match(callback_data) for pattern in patterns)


def test_manual_receipt_review_callback_is_resource_bound():
    assert _matches(ORDER_ID_PATTERNS, "manual_receipt_review_123")


def test_receipt_upload_callback_is_resource_bound():
    assert _matches(ORDER_ID_PATTERNS, "upload_receipt_123")


def test_wallet_callbacks_are_resource_bound():
    assert _matches(WALLET_ID_PATTERNS, "del_addr_123")


def test_unrelated_callbacks_are_not_resource_bound():
    assert not _matches(ORDER_ID_PATTERNS, "menu_feedback")
    assert not _matches(WALLET_ID_PATTERNS, "menu_feedback")
