from pathlib import Path
import unittest


class OrderCurrencyFlowSourceTests(unittest.TestCase):
    def test_authoritative_order_input_uses_decimal_and_canonical_fee_keys(self):
        source = Path(__file__).resolve().parents[1].joinpath("handlers", "order_amount_policy.py").read_text(encoding="utf-8")
        currency_source = Path(__file__).resolve().parents[1].joinpath("handlers", "payment_currency_policy.py").read_text(encoding="utf-8")

        self.assertIn("from decimal import Decimal, InvalidOperation", source)
        self.assertIn("amount = Decimal(callback.data.removeprefix(\"amount_preset_\"))", source)
        self.assertIn("amount = Decimal((message.text or \"\").strip().replace(\",\", \"\"))", source)

        canonical_keys = (
            "base_amount",
            "service_fee_usdt",
            "fixed_network_fee_usdt",
            "total_fee_usdt",
            "total_amount",
        )
        for key in canonical_keys:
            self.assertIn(f"calculation[\"{key}\"]", currency_source)
            self.assertIn(f"calculation['{key}']", currency_source)

        self.assertNotIn("calculation['fee_amount']", currency_source)
        self.assertNotIn('calculation["fee_amount"]', currency_source)
        self.assertNotIn("new_syr_amount", currency_source)
        self.assertNotIn("new_syr_fee", currency_source)
        self.assertNotIn("new_syr_total", currency_source)

    def test_back_to_wallet_keeps_wallet_selection_as_the_active_fsm_step(self):
        source = Path(__file__).resolve().parents[1].joinpath("handlers", "order_wallet_policy.py").read_text(encoding="utf-8")

        marker = 'async def back_to_wallet_selection'
        start = source.index(marker)
        end = source.index('@router.callback_query(F.data == "order_wallet_manual")', start)
        block = source[start:end]

        self.assertIn("await state.set_state(OrderStates.waiting_wallet)", block)
        self.assertNotIn("await state.set_state(OrderStates.waiting_currency)", block)
        self.assertIn('F.data.startswith("currency_")', source)
        self.assertIn("reject_currency_before_wallet", source)


if __name__ == "__main__":
    unittest.main()
