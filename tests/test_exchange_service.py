import unittest
from decimal import Decimal

from services.exchange_service import FIXED_SERVICE_FEE_USDT, ExchangeService
from services.settings_service import SettingsService


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, rate, rate_currency="NEW.SYP"):
        self.rate = rate
        self.rate_currency = rate_currency

    async def fetchrow(self, query, *args):
        if self.rate is None:
            return None
        return {"rate": self.rate, "rate_currency": self.rate_currency}


class FakePool:
    def __init__(self, rate, rate_currency="NEW.SYP"):
        self.conn = FakeConnection(rate, rate_currency)

    def acquire(self):
        return FakeAcquire(self.conn)


class ExchangeServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SettingsService._cache = {
            "service_fee_percent_bep20": "10",
            "service_fee_percent_trc20": "5",
            "service_fee_percent_arb": "8",
            "service_fee_percent_solana": "6",
            "service_fee_percent_eth": "9",
            "service_fee_percent_polygon": "7",
        }
        SettingsService._initialized = True

    async def test_usd_uses_fixed_fee_and_two_decimal_usdt(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "USD", "BEP20")
        self.assertEqual(quote["requested_amount_usdt"], Decimal("100.00"))
        self.assertEqual(quote["fee_percent"], Decimal("0"))
        self.assertEqual(quote["fee_usdt"], FIXED_SERVICE_FEE_USDT)
        self.assertEqual(quote["fee_amount"], Decimal("0.04"))
        self.assertEqual(quote["net_amount_usdt"], Decimal("99.96"))
        self.assertEqual(quote["total_amount"], Decimal("100.00"))

    async def test_fixed_fee_is_identical_across_networks(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quotes = [await service.calculate_order(Decimal("100"), "USD", network) for network in service.SUPPORTED_NETWORKS]
        for quote in quotes:
            self.assertEqual(quote["fee_usdt"], Decimal("0.04"))
            self.assertEqual(quote["net_amount_usdt"], Decimal("99.96"))
            self.assertEqual(quote["fee_percent"], Decimal("0"))

    async def test_new_syp_fixed_fee_is_converted_for_payment_display(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "NEW.SYP", "BEP20")
        self.assertEqual(quote["base_amount"], Decimal("15000.00"))
        self.assertEqual(quote["fee_usdt"], Decimal("0.04"))
        self.assertEqual(quote["fee_amount"], Decimal("6.00"))
        self.assertEqual(quote["net_amount_usdt"], Decimal("99.96"))
        self.assertEqual(quote["total_amount"], Decimal("15000.00"))

    async def test_fixed_fee_is_not_admin_configurable_as_percentage(self):
        with self.assertRaisesRegex(ValueError, "fixed at 0.04 USDT"):
            await __import__("services.operational_policy_service", fromlist=["OperationalPolicyService"]).OperationalPolicyService.set_fee_percent(10, 1, network="BEP20")

    async def test_removed_ton_network_blocks_quote(self):
        service = ExchangeService(FakePool(Decimal("150")))
        with self.assertRaisesRegex(ValueError, "Unsupported network"):
            await service.calculate_order(Decimal("100"), "USD", "TON")

    async def test_legacy_syp_alias_normalizes_without_second_currency(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "SYP", "TRC20")
        self.assertEqual(quote["payment_currency"], "NEW.SYP")
        self.assertEqual(quote["base_amount"], Decimal("15000.00"))
        self.assertEqual(quote["fee_usdt"], Decimal("0.04"))
        self.assertEqual(quote["net_amount_usdt"], Decimal("99.96"))

    async def test_legacy_rate_is_normalized_once(self):
        service = ExchangeService(FakePool(Decimal("15000"), "SYP"))
        quote = await service.calculate_order(Decimal("100"), "NEW.SYP", "BEP20")
        self.assertEqual(quote["exchange_rate"], Decimal("150.00000000"))
        self.assertEqual(quote["base_amount"], Decimal("15000.00"))
        self.assertEqual(quote["fee_usdt"], Decimal("0.04"))

    async def test_missing_rate_blocks_quote(self):
        service = ExchangeService(FakePool(None))
        with self.assertRaisesRegex(ValueError, "Exchange rate is unavailable"):
            await service.calculate_order(Decimal("100"), "NEW.SYP", "BEP20")

    async def test_unsupported_network_blocks_quote(self):
        service = ExchangeService(FakePool(Decimal("150")))
        with self.assertRaisesRegex(ValueError, "Unsupported network"):
            await service.calculate_order(Decimal("100"), "USD", "UNKNOWN")

    async def test_amount_at_or_below_fixed_fee_is_rejected(self):
        service = ExchangeService(FakePool(Decimal("150")))
        with self.assertRaisesRegex(ValueError, "Service fee leaves no positive USDT amount"):
            await service.calculate_order(Decimal("0.04"), "USD", "BEP20")


if __name__ == "__main__":
    unittest.main()
