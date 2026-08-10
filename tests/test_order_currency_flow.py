from pathlib import Path
import unittest


class OrderCurrencyFlowSourceTests(unittest.TestCase):
    def test_order_input_uses_decimal_and_new_syp_display_keys(self):
        source = Path(__file__).resolve().parents[1].joinpath("handlers", "order.py").read_text(encoding="utf-8")

        self.assertIn("from decimal import Decimal, InvalidOperation", source)
        self.assertIn("amount = Decimal(callback.data.replace(\"amount_preset_\", \"\"))", source)
        self.assertIn("amount = Decimal(amount_text)", source)
        self.assertIn("if currency == 'NEW.SYP':", source)
        self.assertIn("calculation['base_amount']", source)
        self.assertIn("calculation['fee_amount']", source)
        self.assertIn("calculation['total_amount']", source)
        self.assertNotIn("calculation['new_syr_amount']", source)
        self.assertNotIn("calculation['new_syr_fee']", source)
        self.assertNotIn("calculation['new_syr_total']", source)


if __name__ == "__main__":
    unittest.main()
