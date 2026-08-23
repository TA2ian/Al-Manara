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

    def test_legacy_receipt_transition_router_is_removed_from_authoritative_surface(self):
        self.assertFalse((ROOT / "handlers/receipt_transition_policy.py").exists())
        bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertNotIn("receipt_transition_policy", bot_source)

    def test_manual_review_callback_is_owned_by_customer_receipt_entrypoint(self):
        source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
        self.assertIn('F.data.startswith("manual_receipt_review_")', source)
        self.assertIn("request_manual_receipt_review", source)
        self.assertIn("await callback.message.edit_reply_markup(reply_markup=None)", source)


if __name__ == "__main__":
    unittest.main()
