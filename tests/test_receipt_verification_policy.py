from decimal import Decimal

import pytest

from services.receipt_verification_policy import AMOUNT_TOLERANCE, amount_tolerance, amounts_match


def test_receipt_amount_tolerance_is_fixed():
    assert AMOUNT_TOLERANCE == Decimal("0.04")
    assert amount_tolerance(Decimal("100")) == Decimal("0.04")
    assert amount_tolerance(Decimal("10000")) == Decimal("0.04")


def test_receipt_amount_match_uses_fixed_tolerance_boundary():
    assert amounts_match(100.04, 100)
    assert amounts_match(99.96, 100)
    assert not amounts_match(100.05, 100)
    assert not amounts_match(99.95, 100)


def test_receipt_amount_match_does_not_scale_tolerance_with_amount():
    assert amounts_match(10000.04, 10000)
    assert not amounts_match(10000.05, 10000)
    assert not amounts_match(10100, 10000)


def test_receipt_amount_match_rejects_non_positive_values():
    assert not amounts_match(0, 100)
    assert not amounts_match(100, 0)
    assert not amounts_match(-1, 100)


def test_receipt_amount_tolerance_rejects_negative_expected_amounts():
    with pytest.raises(ValueError):
        amount_tolerance(-1)
