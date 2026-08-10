"""Exchange-rate and exact financial calculation service."""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

logger = logging.getLogger(__name__)
MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.00000001")


def to_decimal(value, default: str = "0") -> Decimal:
    """Convert numeric input through its string representation to avoid float artifacts."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


class ExchangeService:
    """Manage exchange rates and calculate orders without binary floating-point arithmetic."""

    def __init__(self, db_pool):
        self._db = db_pool
        self._cache = {}
        self._cache_time = None

    async def get_current_rate(self) -> Optional[Decimal]:
        """Get current USD/SYP rate as Decimal."""
        if self._cache_time and (datetime.now() - self._cache_time).total_seconds() < 3600:
            return self._cache.get('rate')

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT rate FROM exchange_rates ORDER BY updated_at DESC LIMIT 1"
            )

            if row:
                self._cache['rate'] = to_decimal(row['rate'])
                self._cache_time = datetime.now()
                return self._cache['rate']

            return Decimal("15000.00")

    async def update_rate(self, rate, admin_id: int) -> bool:
        """Update exchange rate after strict positive-value validation."""
        try:
            value = to_decimal(rate)
            if value <= 0:
                return False
            value = value.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)
            async with self._db.acquire() as conn:
                await conn.execute(
                    "INSERT INTO exchange_rates (rate, updated_by) VALUES ($1, $2)",
                    value, admin_id
                )

            self._cache = {}
            self._cache_time = None
            return True
        except Exception as e:
            logger.error(f"Rate update failed: {e}")
            return False

    async def calculate_order(self, amount_usdt, currency: str) -> dict:
        """Calculate order totals using Decimal and explicit two-decimal money rounding."""
        amount = to_decimal(amount_usdt)
        if amount <= 0:
            raise ValueError("amount_usdt must be positive")
        if currency not in {"USD", "SYP"}:
            raise ValueError("Unsupported payment currency")

        rate = await self.get_current_rate()
        if rate is None or rate <= 0:
            raise ValueError("Exchange rate is unavailable")

        if currency == 'USD':
            base_amount = amount
        else:
            base_amount = amount * rate

        from config import Config
        fee_percent = to_decimal(Config.SERVICE_FEE_PERCENT)
        fee_fixed = to_decimal(Config.SERVICE_FEE_FIXED) if currency == 'SYP' else Decimal("0")

        fee_amount = (base_amount * fee_percent / Decimal("100")) + fee_fixed
        base_amount = base_amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        fee_amount = fee_amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        total = (base_amount + fee_amount).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

        if currency == 'SYP':
            new_syr_amount = (base_amount / Decimal("100")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            new_syr_fee = (fee_amount / Decimal("100")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            new_syr_total = (total / Decimal("100")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        else:
            new_syr_amount = Decimal("0")
            new_syr_fee = Decimal("0")
            new_syr_total = Decimal("0")

        return {
            'amount_usdt': amount,
            'exchange_rate': rate,
            'payment_currency': currency,
            'base_amount': base_amount,
            'fee_percent': fee_percent,
            'fee_amount': fee_amount,
            'total_amount': total,
            'new_syr_amount': new_syr_amount,
            'new_syr_fee': new_syr_fee,
            'new_syr_total': new_syr_total,
        }
