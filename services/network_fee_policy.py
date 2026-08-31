"""Network-specific fee policy and transaction amount tolerance."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


SUPPORTED_NETWORKS = ("BEP20", "TRC20", "ARB", "SOLANA", "ETH", "POLYGON")
MONEY_QUANT = Decimal("0.01")
USDT_QUANT = Decimal("0.01")
AMOUNT_TOLERANCE_USDT = Decimal("0.04")


@dataclass(frozen=True)
class NetworkFeePolicy:
    network: str
    service_fee_percent: Decimal
    fixed_network_fee_usdt: Decimal

    def __post_init__(self) -> None:
        if self.network not in SUPPORTED_NETWORKS:
            raise ValueError("Unsupported network")
        if not self.service_fee_percent.is_finite() or not self.fixed_network_fee_usdt.is_finite():
            raise ValueError("Fee values must be finite")
        if self.service_fee_percent < 0 or self.fixed_network_fee_usdt < 0:
            raise ValueError("Fee values cannot be negative")

    def calculate(self, requested_amount_usdt: Decimal) -> dict[str, Decimal]:
        amount = Decimal(str(requested_amount_usdt)).quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
        if amount <= 0:
            raise ValueError("Requested amount must be positive")
        service_fee = (amount * self.service_fee_percent / Decimal("100")).quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
        fixed_fee = self.fixed_network_fee_usdt.quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
        total_fee = service_fee + fixed_fee
        net_amount = (amount - total_fee).quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
        if net_amount <= 0:
            raise ValueError("Fees leave no positive user amount")
        return {
            "requested_amount_usdt": amount,
            "service_fee_percent": self.service_fee_percent,
            "service_fee_usdt": service_fee,
            "fixed_network_fee_usdt": fixed_fee,
            "total_fee_usdt": total_fee,
            "net_amount_usdt": net_amount,
        }


def amount_within_tolerance(actual: Decimal, expected: Decimal) -> bool:
    """Compare on-chain USDT against the expected amount using the business tolerance."""
    try:
        actual_value = Decimal(str(actual)).quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
        expected_value = Decimal(str(expected)).quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid transaction amount") from exc
    if not actual_value.is_finite() or not expected_value.is_finite():
        return False
    return abs(actual_value - expected_value) <= AMOUNT_TOLERANCE_USDT


def parse_non_negative_decimal(value: object, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid number") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return parsed
