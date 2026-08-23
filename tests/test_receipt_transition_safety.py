import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReceiptTransitionSafetyTests(unittest.TestCase):
    def test_receipt_upload_delegates_to_canonical_service_without_direct_status_assignment(self):
        source = (ROOT / "handlers/receipt_processing_policy.py").read_text(encoding="utf-8")
        self.assertIn("handle_receipt_upload", source)
        self.assertIn("from services.receipt_service import handle_receipt_upload", source)
        self.assertNotIn("SET status = 'receipt_received'", source)
        self.assertNotIn("UPDATE orders SET status", source)

    def test_manual_review_refetches_joined_customer_data(self):
        source = (ROOT / "handlers/receipt_transition_policy.py").read_text(encoding="utf-8")
        self.assertIn("u.full_name", source)
        self.assertIn("u.shamcash_account", source)


if __name__ == "__main__":
    unittest.main()
