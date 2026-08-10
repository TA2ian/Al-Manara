import unittest
from decimal import Decimal

from services.exchange_service import ExchangeService


class CurrencyModelTests(unittest.TestCase):
    def test_old_syp_is_display_only_equivalent(self):
        self.assertEqual(
            ExchangeService.old_syp_equivalent(Decimal("150.00")),
            Decimal("15000.00"),
        )

    def test_legacy_rate_can_be_normalized(self):
        legacy = Decimal("15000")
        normalized = (legacy / Decimal("100")).quantize(Decimal("0.00000001"))
        self.assertEqual(normalized, Decimal("150.00000000"))

    def test_payment_currency_model_is_new_syp(self):
        self.assertIn("NEW.SYP", ExchangeService.SUPPORTED_PAYMENT_CURRENCIES)
        self.assertNotIn("SYP", ExchangeService.SUPPORTED_PAYMENT_CURRENCIES)


if __name__ == "__main__":
    unittest.main()
