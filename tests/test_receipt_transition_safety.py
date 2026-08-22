import unittest
from pathlib import Path


class ReceiptTransitionSafetyTests(unittest.TestCase):
    def test_receipt_upload_does_not_directly_assign_status(self):
        source = Path("handlers/my_orders.py").read_text(encoding="utf-8")
        self.assertIn("transition_order(", source)
        self.assertNotIn("SET status = 'receipt_received'", source)

    def test_manual_review_refetches_joined_customer_data(self):
        source = Path("handlers/receipt_transition_policy.py").read_text(encoding="utf-8")
        self.assertIn("u.full_name", source)
        self.assertIn("u.shamcash_account", source)


if __name__ == "__main__":
    unittest.main()
