import unittest
from decimal import Decimal

from services.exchange_service import ExchangeService


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, rate):
        self.rate = rate

    async def fetchrow(self, query, *args):
        if self.rate is None:
            return None
        return {"rate": self.rate}


class FakePool:
    def __init__(self, rate):
        self.conn = FakeConnection(rate)

    def acquire(self):
        return FakeAcquire(self.conn)


class ExchangeServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_syp_is_canonical_payment_currency(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "NEW.SYP")

        self.assertEqual(quote["payment_currency"], "NEW.SYP")
        self.assertEqual(quote["exchange_rate"], Decimal("150"))
        self.assertEqual(quote["base_amount"], Decimal("15000.00"))
        self.assertEqual(quote["old_syp_amount"], Decimal("1500000.00"))

    async def test_legacy_syp_alias_normalizes_without_creating_second_currency(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "SYP")

        self.assertEqual(quote["payment_currency"], "NEW.SYP")
        self.assertEqual(quote["base_amount"], Decimal("15000.00"))

    async def test_legacy_rate_is_normalized_once(self):
        service = ExchangeService(FakePool(Decimal("15000")))
        quote = await service.calculate_order(Decimal("100"), "NEW.SYP")

        self.assertEqual(quote["exchange_rate"], Decimal("150.00000000"))
        self.assertEqual(quote["base_amount"], Decimal("15000.00"))

    async def test_fee_is_added_exactly_once(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "NEW.SYP")

        self.assertEqual(
            quote["total_amount"],
            quote["base_amount"] + quote["fee_amount"],
        )
        self.assertEqual(
            quote["old_syp_total"],
            quote["old_syp_amount"] + quote["old_syp_fee"],
        )

    async def test_usd_does_not_apply_syp_conversion(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "USD")

        self.assertEqual(quote["payment_currency"], "USD")
        self.assertEqual(quote["base_amount"], Decimal("100.00"))
        self.assertEqual(quote["old_syp_amount"], Decimal("0"))

    async def test_missing_rate_blocks_quote(self):
        service = ExchangeService(FakePool(None))
        with self.assertRaisesRegex(ValueError, "Exchange rate is unavailable"):
            await service.calculate_order(Decimal("100"), "NEW.SYP")


if __name__ == "__main__":
    unittest.main()
