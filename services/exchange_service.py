"""Exchange-rate and exact financial calculation service."""
import logging
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from services.operational_policy_service import OperationalPolicyService

logger = logging.getLogger(__name__)
MONEY_QUANT = Decimal("0.01")
USDT_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.00000001")


class ExchangeService:
    """Manage exchange rates and exact financial calculations."""

    SUPPORTED_PAYMENT_CURRENCIES = {"USD", "NEW.SYP"}
    SUPPORTED_NETWORKS = {"BEP20", "TRC20", "ARB", "SOLANA", "ETH", "POLYGON"}
    NETWORK_ALIASES = {"ERC20": "ETH", "ETHEREUM": "ETH", "ARBITRUM": "ARB", "SOL": "SOLANA", "MATIC": "POLYGON", "POL": "POLYGON"}

    def __init__(self, db_pool):
        self._db = db_pool
        self._cache = {}
        self._cache_monotonic = None

    @staticmethod
    def to_decimal(value, default: str = "0") -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal(default)

    @classmethod
    def normalize_network(cls, network: str | None) -> str:
        value = (network or "BEP20").strip().upper()
        return cls.NETWORK_ALIASES.get(value, value)

    async def get_current_rate(self) -> Optional[Decimal]:
        now = time.monotonic()
        if self._cache_monotonic is not None and now - self._cache_monotonic < 3600:
            return self._cache.get("rate")
        async with self._db.acquire() as conn:
            row = await conn.fetchrow("SELECT rate, COALESCE(rate_currency, 'NEW.SYP') AS rate_currency FROM exchange_rates ORDER BY updated_at DESC LIMIT 1")
            if not row:
                return None
            rate = self.to_decimal(row["rate"])
            currency = (row["rate_currency"] or "NEW.SYP").upper()
            if currency != "NEW.SYP":
                logger.error("Unsupported exchange-rate currency in DB: %s", currency)
                return None
            if rate <= 0:
                return None
            self._cache["rate"] = rate
            self._cache_monotonic = now
            return rate

    async def update_rate(self, rate, admin_id: int) -> bool:
        try:
            value = self.to_decimal(rate)
            if value <= 0:
                return False
            value = value.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)
            async with self._db.acquire() as conn:
                await conn.execute("INSERT INTO exchange_rates (rate, rate_currency, updated_by) VALUES ($1, 'NEW.SYP', $2)", value, admin_id)
            self._cache = {}
            self._cache_monotonic = None
            return True
        except Exception as exc:
            logger.error("Rate update failed: %s", exc)
            return False

    async def calculate_order(self, amount_usdt, currency: str, network: str | None = None) -> dict:
        """Calculate a quote using network-specific service and fixed fees."""
        currency = currency.upper()
        normalized_network = self.normalize_network(network)
        amount = self.to_decimal(amount_usdt)
        if amount <= 0:
            raise ValueError("amount_usdt must be positive")
        if currency not in self.SUPPORTED_PAYMENT_CURRENCIES:
            raise ValueError("Unsupported payment currency")
        if normalized_network not in self.SUPPORTED_NETWORKS:
            raise ValueError("Unsupported network")
        rate = await self.get_current_rate()
        if rate is None or rate <= 0:
            raise ValueError("Exchange rate is unavailable")

        amount_usdt_rounded = amount.quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
        policy = await OperationalPolicyService.get_network_fee_policy(normalized_network)
        calculation = policy.calculate(amount_usdt_rounded)
        service_fee_usdt = calculation["service_fee_usdt"]
        fixed_network_fee_usdt = calculation["fixed_network_fee_usdt"]
        total_fee_usdt = calculation["total_fee_usdt"]
        net_amount_usdt = calculation["net_amount_usdt"]
        base_amount = amount_usdt_rounded if currency == "USD" else (amount_usdt_rounded * rate).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        fee_amount = total_fee_usdt if currency == "USD" else (total_fee_usdt * rate).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        return {
            "requested_amount_usdt": calculation["requested_amount_usdt"],
            "amount_usdt": net_amount_usdt,
            "net_amount_usdt": net_amount_usdt,
            "exchange_rate": rate,
            "payment_currency": currency,
            "network": normalized_network,
            "base_amount": base_amount,
            "service_fee_percent": policy.service_fee_percent,
            "fee_percent": policy.service_fee_percent,
            "service_fee_usdt": service_fee_usdt,
            "fixed_network_fee_usdt": fixed_network_fee_usdt,
            "total_fee_usdt": total_fee_usdt,
            "fee_usdt": total_fee_usdt,
            "fee_amount": fee_amount,
            "fixed_fee_usdt": fixed_network_fee_usdt,
            "total_amount": base_amount,
        }
