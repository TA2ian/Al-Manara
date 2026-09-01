import unittest

from services.exchange_service import ExchangeService


class CurrencyModelTests(unittest.TestCase):
    def test_payment_currency_model_is_new_syp(self):
        self.assertIn("NEW.SYP", ExchangeService.SUPPORTED_PAYMENT_CURRENCIES)
        self.assertNotIn("SYP", ExchangeService.SUPPORTED_PAYMENT_CURRENCIES)


if __name__ == "__main__":
    unittest.main()
