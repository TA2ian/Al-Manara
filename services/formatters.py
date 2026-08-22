"""Centralized customer/admin numeric formatting policy."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


USDT_QUANT = Decimal("0.001")
MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.01")


def to_decimal(value, default: str = "0") -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _format(value, quant: Decimal) -> str:
    number = to_decimal(value).quantize(quant, rounding=ROUND_HALF_UP)
    return f"{number:,.{abs(quant.as_tuple().exponent)}f}"


def usdt(value) -> str:
    """USDT amounts: exactly three decimals."""
    return _format(value, USDT_QUANT)


def money(value) -> str:
    """Fiat/payment amounts: exactly two decimals."""
    return _format(value, MONEY_QUANT)


def rate(value) -> str:
    """Displayed exchange rates: exactly two decimals."""
    return _format(value, RATE_QUANT)


def percent(value) -> str:
    """Percentages: two decimals, without meaningless trailing zeros."""
    number = to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    text = f"{number:,.2f}"
    return text.rstrip("0").rstrip(".")
