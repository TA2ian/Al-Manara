"""Exchange rate service."""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ExchangeService:
    """Manage exchange rates."""

    def __init__(self, db_pool):
        self._db = db_pool
        self._cache = {}
        self._cache_time = None

    async def get_current_rate(self) -> Optional[float]:
        """Get current USD/SYP rate."""
        # Check cache first (1 hour)
        if self._cache_time and (datetime.now() - self._cache_time).seconds < 3600:
            return self._cache.get('rate')

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT rate FROM exchange_rates ORDER BY updated_at DESC LIMIT 1"
            )

            if row:
                self._cache['rate'] = row['rate']
                self._cache_time = datetime.now()
                return row['rate']

            # Default rate
            return 15000.0

    async def update_rate(self, rate: float, admin_id: int) -> bool:
        """Update exchange rate."""
        try:
            async with self._db.acquire() as conn:
                await conn.execute(
                    "INSERT INTO exchange_rates (rate, updated_by) VALUES ($1, $2)",
                    rate, admin_id
                )

            # Invalidate cache
            self._cache = {}
            self._cache_time = None

            return True
        except Exception as e:
            logger.error(f"Rate update failed: {e}")
            return False

    async def calculate_order(self, amount_usdt: float, currency: str) -> dict:
        """Calculate order totals."""
        rate = await self.get_current_rate()

        # Calculate base amount
        if currency == 'USD':
            base_amount = amount_usdt
        else:  # SYP
            base_amount = amount_usdt * rate

        # Get fee settings from config
        from config import Config
        fee_percent = Config.SERVICE_FEE_PERCENT
        fee_fixed = Config.SERVICE_FEE_FIXED if currency == 'SYP' else 0

        fee_amount = (base_amount * fee_percent / 100) + fee_fixed
        total = base_amount + fee_amount

        return {
            'amount_usdt': amount_usdt,
            'exchange_rate': rate,
            'payment_currency': currency,
            'base_amount': base_amount,
            'fee_percent': fee_percent,
            'fee_amount': fee_amount,
            'total_amount': total
        }
