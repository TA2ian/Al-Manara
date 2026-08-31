from decimal import Decimal

import pytest

from services.receipt_verification_policy import AMOUNT_TOLERANCE_PERCENT, amount_tolerance, amounts_match


def test_receipt_amount_tolerance_is_canonical_two_percent():
    assert AMOUNT_TOLERANCE_PERCENT == Decimal("0.02")
    assert amount_tolerance(Decimal("100")) == Decimal("2.00")


def test_receipt_amount_match_uses_the_canonical_tolerance_boundary():
    assert amounts_match(102, 100)
    assert amounts_match(98, 100)
    assert not amounts_match(102.01, 100)
    assert not amounts_match(97.99, 100)


def test_receipt_amount_match_rejects_non_positive_values():
    assert not amounts_match(0, 100)
    assert not amounts_match(100, 0)
    assert not amounts_match(-1, 100)


def test_receipt_amount_tolerance_rejects_negative_expected_amounts():
    with pytest.raises(ValueError):
        amount_tolerance(-1)
