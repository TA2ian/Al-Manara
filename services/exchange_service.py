"""Exchange-rate and exact financial calculation service."""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from config import Config
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)
MONEY_QUANT = Decimal("0.01")
USDT_QUANT = Decimal("0.00000001")
RATE_QUANT = Decimal("0.00000001")
OLD_SYP_PER_NEW_SYP = Decimal("100")


class ExchangeService:
    """Manage payment rates and immutable order quotes."""

    SUPPORTED_PAYMENT_CURRENCIES = {"USD", "NEW.SYP"}
    SUPPORTED_NETWORKS = {"BEP20", "TRC20", "TON", "ARB", "SOLANA", "ETH"}
    NETWORK_ALIASES = {"SYP": "NEW.SYP", "ERC20": "ETH", "ARBITRUM": "ARB", "SOL": "SOLANA"}

    def __init__(self, db_pool):
        self._db = db_pool
        self._cache = {}
        self._cache_time = None

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
        if self._cache_time and (datetime.now() - self._cache_time).total_seconds() < 3600:
            return self._cache.get("rate")
        async with self._db.acquire() as conn:
            row = await conn.fetchrow("SELECT rate, COALESCE(rate_currency, 'NEW.SYP') AS rate_currency FROM exchange_rates ORDER BY updated_at DESC LIMIT 1")
            if not row:
                return None
            rate = self.to_decimal(row["rate"])
            currency = (row["rate_currency"] or "NEW.SYP").upper()
            if currency == "SYP":
                rate = (rate / OLD_SYP_PER_NEW_SYP).quantize(RATE_QUANT, rounding=ROUND_HALF_UP)
            elif currency != "NEW.SYP":
                logger.error("Unsupported exchange-rate currency in DB: %s", currency)
                return None
            if rate <= 0:
                return None
            self._cache["rate"] = rate
            self._cache_time = datetime.now()
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
            self._cache_time = None
            return True
        except Exception as exc:
            logger.error("Rate update failed: %s", exc)
            return False

    @staticmethod
    def old_syp_equivalent(new_syp_amount) -> Decimal:
        return (ExchangeService.to_decimal(new_syp_amount) * OLD_SYP_PER_NEW_SYP).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

    @classmethod
    async def get_fee_percent(cls, network: str | None = None) -> Decimal:
        normalized = cls.normalize_network(network)
        fallback = cls.to_decimal(Config.SERVICE_FEE_PERCENT)
        value = await SettingsService.get(f"service_fee_percent_{normalized.lower()}", str(fallback))
        return max(Decimal("0"), min(cls.to_decimal(value, str(fallback)), Decimal("100")))

    async def calculate_order(self, amount_usdt, currency: str, network: str | None = None) -> dict:
        """Calculate a quote where the entered amount is gross and fees are deducted from it."""
        if currency == "SYP":
            currency = "NEW.SYP"
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
        base_amount = amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if currency == "USD" else (amount * rate).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        fee_percent = await self.get_fee_percent(normalized_network)
        fee_amount = (base_amount * fee_percent / Decimal("100")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        fee_usdt = fee_amount.quantize(USDT_QUANT, rounding=ROUND_HALF_UP) if currency == "USD" else (fee_amount / rate).quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
        net_amount_usdt = (amount - fee_usdt).quantize(USDT_QUANT, rounding=ROUND_HALF_UP)
        if net_amount_usdt <= 0:
            raise ValueError("Service fee leaves no positive USDT amount")
        old_syp_amount = self.old_syp_equivalent(base_amount) if currency == "NEW.SYP" else Decimal("0")
        old_syp_fee = self.old_syp_equivalent(fee_amount) if currency == "NEW.SYP" else Decimal("0")
        return {
            "requested_amount_usdt": amount,
            "amount_usdt": net_amount_usdt,
            "net_amount_usdt": net_amount_usdt,
            "exchange_rate": rate,
            "payment_currency": currency,
            "network": normalized_network,
            "base_amount": base_amount,
            "fee_percent": fee_percent,
            "fee_amount": fee_amount,
            "fee_usdt": fee_usdt,
            "total_amount": base_amount,
            "old_syp_amount": old_syp_amount,
            "old_syp_fee": old_syp_fee,
            "old_syp_total": old_syp_amount,
        }
