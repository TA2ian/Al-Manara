import unittest
from decimal import Decimal

from services.formatters import money, percent, rate, usdt


class FormatterTests(unittest.TestCase):
    def test_usdt_is_two_business_decimals(self):
        self.assertEqual(usdt(50), "50.00")
        self.assertEqual(usdt(Decimal("50.1239")), "50.12")
        self.assertEqual(usdt(Decimal("50.125")), "50.13")

    def test_money_is_two_decimals(self):
        self.assertEqual(money("55"), "55.00")
        self.assertEqual(money(Decimal("55.678")), "55.68")

    def test_rate_is_two_decimals(self):
        self.assertEqual(rate("150.5"), "150.50")

    def test_percent_removes_meaningless_zeroes(self):
        self.assertEqual(percent("2.000000"), "2")
        self.assertEqual(percent("2.5"), "2.5")


if __name__ == "__main__":
    unittest.main()
