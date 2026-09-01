import unittest
from decimal import Decimal
from unittest.mock import patch

from services.exchange_service import ExchangeService
from services.operational_policy_service import OperationalPolicyService
from services.network_fee_policy import AMOUNT_TOLERANCE_USDT
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


async def cache_setting(key: str, value: str):
    SettingsService._cache[key] = value
    SettingsService._initialized = True


class ExchangeServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SettingsService._cache = {
            "service_fee_percent_bep20": "10",
            "service_fee_percent_trc20": "5",
            "service_fee_percent_arb": "8",
            "service_fee_percent_solana": "6",
            "service_fee_percent_eth": "9",
            "service_fee_percent_polygon": "7",
            "fixed_network_fee_usdt_bep20": "0.20",
            "fixed_network_fee_usdt_trc20": "1.00",
            "fixed_network_fee_usdt_arb": "0.30",
            "fixed_network_fee_usdt_solana": "0.01",
            "fixed_network_fee_usdt_eth": "5.00",
            "fixed_network_fee_usdt_polygon": "0.40",
        }
        SettingsService._initialized = True
        self._settings_set_patch = patch.object(SettingsService, "set", new=cache_setting)
        self._settings_set_patch.start()
        self.addCleanup(self._settings_set_patch.stop)

    async def test_usd_combines_network_service_and_fixed_fees(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "USD", "BEP20")
        self.assertEqual(quote["requested_amount_usdt"], Decimal("100.00"))
        self.assertEqual(quote["service_fee_percent"], Decimal("10"))
        self.assertEqual(quote["service_fee_usdt"], Decimal("10.00"))
        self.assertEqual(quote["fixed_network_fee_usdt"], Decimal("0.20"))
        self.assertEqual(quote["total_fee_usdt"], Decimal("10.20"))
        self.assertEqual(quote["net_amount_usdt"], Decimal("89.80"))
        self.assertEqual(quote["total_fee_usdt"], Decimal("10.20"))
        self.assertEqual(quote["total_amount"], Decimal("100.00"))

    async def test_networks_have_independent_service_and_fixed_fees(self):
        service = ExchangeService(FakePool(Decimal("150")))
        expected = {
            "BEP20": (Decimal("10"), Decimal("0.20")),
            "TRC20": (Decimal("5"), Decimal("1.00")),
            "ARB": (Decimal("8"), Decimal("0.30")),
            "SOLANA": (Decimal("6"), Decimal("0.01")),
            "ETH": (Decimal("9"), Decimal("5.00")),
            "POLYGON": (Decimal("7"), Decimal("0.40")),
        }
        for network, (service_percent, fixed_fee) in expected.items():
            quote = await service.calculate_order(Decimal("100"), "USD", network)
            self.assertEqual(quote["service_fee_percent"], service_percent)
            self.assertEqual(quote["fixed_network_fee_usdt"], fixed_fee)
            self.assertEqual(quote["total_fee_usdt"], service_percent + fixed_fee)

    async def test_new_syp_converts_combined_fees_for_payment_display(self):
        service = ExchangeService(FakePool(Decimal("150")))
        quote = await service.calculate_order(Decimal("100"), "NEW.SYP", "BEP20")
        self.assertEqual(quote["base_amount"], Decimal("15000.00"))
        self.assertEqual(quote["service_fee_usdt"], Decimal("10.00"))
        self.assertEqual(quote["fixed_network_fee_usdt"], Decimal("0.20"))
        self.assertEqual(quote["total_fee_usdt"], Decimal("10.20"))
        self.assertEqual(quote["total_fee_payment_currency"], Decimal("1530.00"))
        self.assertEqual(quote["net_amount_usdt"], Decimal("89.80"))
        self.assertEqual(quote["total_amount"], Decimal("15000.00"))

    async def test_service_fee_can_be_changed_per_network_by_admin(self):
        saved = await OperationalPolicyService.set_fee_percent("12.5", 1, network="BEP20")
        self.assertEqual(saved, Decimal("12.5"))
        policy = await OperationalPolicyService.get_network_fee_policy("BEP20")
        self.assertEqual(policy.service_fee_percent, Decimal("12.5"))
        self.assertEqual(policy.fixed_network_fee_usdt, Decimal("0.20"))

    async def test_fixed_network_fee_can_be_changed_per_network_by_admin(self):
        saved = await OperationalPolicyService.set_fixed_fee_usdt("0.75", 1, network="BEP20")
        self.assertEqual(saved, Decimal("0.75"))
        self.assertEqual(await OperationalPolicyService.get_fixed_fee_usdt("BEP20"), Decimal("0.75"))

    async def test_tolerance_is_not_a_fee(self):
        quote = await ExchangeService(FakePool(Decimal("150"))).calculate_order(Decimal("100"), "USD", "BEP20")
        self.assertNotEqual(quote["total_fee_usdt"], AMOUNT_TOLERANCE_USDT)

    async def test_removed_ton_network_blocks_quote(self):
        service = ExchangeService(FakePool(Decimal("150")))
        with self.assertRaisesRegex(ValueError, "Unsupported network"):
            await service.calculate_order(Decimal("100"), "USD", "TON")

    async def test_missing_rate_blocks_quote(self):
        service = ExchangeService(FakePool(None))
        with self.assertRaisesRegex(ValueError, "Exchange rate is unavailable"):
            await service.calculate_order(Decimal("100"), "NEW.SYP", "BEP20")

    async def test_unsupported_network_blocks_quote(self):
        service = ExchangeService(FakePool(Decimal("150")))
        with self.assertRaisesRegex(ValueError, "Unsupported network"):
            await service.calculate_order(Decimal("100"), "USD", "UNKNOWN")

    async def test_fees_that_exhaust_amount_are_rejected(self):
        service = ExchangeService(FakePool(Decimal("150")))
        with self.assertRaisesRegex(ValueError, "Fees leave no positive user amount"):
            await service.calculate_order(Decimal("1"), "USD", "ETH")


if __name__ == "__main__":
    unittest.main()
