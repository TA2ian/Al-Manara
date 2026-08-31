"""Authoritative policy for receipt amount comparison."""
from __future__ import annotations

from decimal import Decimal


AMOUNT_TOLERANCE_PERCENT = Decimal("0.02")


def amount_tolerance(expected_amount: Decimal | float | int) -> Decimal:
    """Return the absolute allowed amount deviation for receipt verification."""
    expected = Decimal(str(expected_amount))
    if expected < 0:
        raise ValueError("expected amount cannot be negative")
    return expected * AMOUNT_TOLERANCE_PERCENT


def amounts_match(extracted_amount: Decimal | float | int, expected_amount: Decimal | float | int) -> bool:
    """Return whether two receipt amounts satisfy the canonical tolerance policy."""
    extracted = Decimal(str(extracted_amount))
    expected = Decimal(str(expected_amount))
    if extracted <= 0 or expected <= 0:
        return False
    return abs(extracted - expected) <= amount_tolerance(expected)
