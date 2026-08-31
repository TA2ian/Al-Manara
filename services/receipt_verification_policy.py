"""Authoritative policy for receipt amount comparison."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

AMOUNT_TOLERANCE = Decimal("0.04")
_MONEY_QUANTUM = Decimal("0.01")


def amount_tolerance(expected_amount: Decimal | float | int) -> Decimal:
    """Return the fixed absolute deviation allowed during receipt verification."""
    expected = Decimal(str(expected_amount))
    if expected < 0:
        raise ValueError("expected amount cannot be negative")
    return AMOUNT_TOLERANCE


def amounts_match(extracted_amount: Decimal | float | int, expected_amount: Decimal | float | int) -> bool:
    """Return whether receipt and expected amounts differ by no more than 0.04."""
    extracted = Decimal(str(extracted_amount))
    expected = Decimal(str(expected_amount))
    if extracted <= 0 or expected <= 0:
        return False
    extracted = extracted.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    expected = expected.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    return abs(extracted - expected) <= AMOUNT_TOLERANCE
