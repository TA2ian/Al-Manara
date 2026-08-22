import unittest
from decimal import Decimal

from services.exchange_service import ExchangeService


class _Conn:
    def __init__(self, row):
        self.row = row

    async def fetchrow(self, *args):
        return self.row


class _Acquire:
    def __init__(self, row):
        self.conn = _Conn(row)

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *args):
        return False


class _Pool:
    def __init__(self, row):
        self.row = row

    def acquire(self):
        return _Acquire(self.row)


class ExchangeRateCurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_canonical_new_syp_rate_is_not_implicitly_divided(self):
        service = ExchangeService(_Pool({"rate": Decimal("1500"), "rate_currency": "NEW.SYP"}))
        self.assertEqual(await service.get_current_rate(), Decimal("1500"))

    async def test_legacy_syp_rate_is_converted_explicitly(self):
        service = ExchangeService(_Pool({"rate": Decimal("150000"), "rate_currency": "SYP"}))
        self.assertEqual(await service.get_current_rate(), Decimal("1500.00000000"))


if __name__ == "__main__":
    unittest.main()
