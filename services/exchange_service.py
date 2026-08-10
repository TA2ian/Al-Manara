"""Exchange-rate and exact financial calculation service."""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

logger = logging.getLogger(__name__)
MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.00000001")
OLD_SYP_PER_NEW_SYP = Decimal("100")


def to_decimal(value, default: str = "0") -> Decimal:
    """Convert numeric input through its string representation to avoid float artifacts."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


class ExchangeService:
    """Manage USD/NEW.SYP rates and calculate immutable order quotes."""

    SUPPORTED_PAYMENT_CURRENCIES = {"USD", "NEW.SYP"}

    def __init__(self, db_pool):
        self._db = db_pool
        self._cache = {}
        self._cache_time = None

    async def get_current_rate(self) -> Optional[Decimal]:
        """Get current USD/NEW.SYP rate as Decimal."""
        if self._cache_time and (datetime.now() - self._cache_time).total_seconds() < 3600:
            return self._cache.get("rate")

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT rate FROM exchange_rates ORDER BY updated_at DESC LIMIT 1"
            )

            if row:
                self._cache["rate"] = to_decimal(row["rate"])
                self._cache_time = datetime.now()
                return self._cache["rate"]

            return Decimal("150.00")

    async def update_rate(self, rate, admin_id: int) -> bool:
        """Update the USD/NEW.SYP rate after strict positive-value validation."""
        try:
            value = to_decimal(rate)
            if value <= 0:
                return False
            value = value.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)
            async with self._db.acquire() as conn:
                await conn.execute(
                    "INSERT INTO exchange_rates (rate, updated_by) VALUES ($1, $2)",
                    value,
                    admin_id,
                )

            self._cache = {}
            self._cache_time = None
            return True
        except Exception as e:
            logger.error("Rate update failed: %s", e)
            return False

    @staticmethod
    def old_syp_equivalent(new_syp_amount) -> Decimal:
        """Return the legacy SYP display equivalent; never use it for payment calculations."""
        return (to_decimal(new_syp_amount) * OLD_SYP_PER_NEW_SYP).quantize(
            MONEY_QUANT, rounding=ROUND_HALF_UP
        )

    async def calculate_order(self, amount_usdt, currency: str) -> dict:
        """Create a quote using the current rate exactly once.

        The returned quote is intended to be stored with the order and reused
        during confirmation/payment. Changing the live rate later must not
        recalculate an existing quote.
        """
        amount = to_decimal(amount_usdt)
        if amount <= 0:
            raise ValueError("amount_usdt must be positive")
        if currency not in self.SUPPORTED_PAYMENT_CURRENCIES:
            raise ValueError("Unsupported payment currency")

        rate = await self.get_current_rate()
        if rate is None or rate <= 0:
            raise ValueError("Exchange rate is unavailable")

        if currency == "USD":
            base_amount = amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        else:
            base_amount = (amount * rate).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

        from config import Config
        fee_percent = to_decimal(Config.SERVICE_FEE_PERCENT)
        fee_amount = (
            base_amount * fee_percent / Decimal("100")
        ).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        total = (base_amount + fee_amount).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

        old_syp_amount = Decimal("0")
        old_syp_fee = Decimal("0")
        old_syp_total = Decimal("0")
        if currency == "NEW.SYP":
            old_syp_amount = self.old_syp_equivalent(base_amount)
            old_syp_fee = self.old_syp_equivalent(fee_amount)
            old_syp_total = self.old_syp_equivalent(total)

        return {
            "amount_usdt": amount,
            "exchange_rate": rate,
            "payment_currency": currency,
            "base_amount": base_amount,
            "fee_percent": fee_percent,
            "fee_amount": fee_amount,
            "total_amount": total,
            "old_syp_amount": old_syp_amount,
            "old_syp_fee": old_syp_fee,
            "old_syp_total": old_syp_total,
        }
