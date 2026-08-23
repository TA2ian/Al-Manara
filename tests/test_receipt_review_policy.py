import unittest
from pathlib import Path

from services.receipt_service import _customer_result_message

ROOT = Path(__file__).resolve().parents[1]


class ReceiptReviewPolicyTests(unittest.TestCase):
    def test_failed_attempt_exposes_manual_review_action(self):
        text, parse_mode, keyboard = _customer_result_message(
            {"score": 20, "score_label": "منخفضة"},
            remaining_attempts=2,
            auto_verified=False,
            order_id=41,
            lang="ar",
        )
        self.assertIn("المراجعة اليدوية", text)
        self.assertEqual(parse_mode, "HTML")
        self.assertIsNotNone(keyboard)
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "manual_receipt_review_41")

    def test_exhausted_attempts_do_not_expose_manual_button(self):
        text, parse_mode, keyboard = _customer_result_message(
            {"score": 0, "score_label": "فاشل"},
            remaining_attempts=0,
            auto_verified=False,
            order_id=41,
            lang="ar",
        )
        self.assertIn("استنفاد", text)
        self.assertEqual(parse_mode, "HTML")
        self.assertIsNone(keyboard)

    def test_automatic_success_does_not_expose_manual_button(self):
        _, _, keyboard = _customer_result_message(
            {"score": 100, "score_label": "عالية"},
            remaining_attempts=2,
            auto_verified=True,
            order_id=41,
            lang="ar",
        )
        self.assertIsNone(keyboard)

    def test_admin_handoff_is_gated_by_success_or_exhaustion(self):
        source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
        self.assertIn("if auto_verified or remaining_attempts <= 0:", source)
        self.assertIn("await notify_admins_receipt(", source)
        self.assertIn("manual_review_requested=True", source)

    def test_progress_pipeline_and_elapsed_timer_are_present(self):
        source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
        self.assertIn("_start_progress", source)
        self.assertIn("_set_progress_stage", source)
        self.assertIn("الزمن المنقضي", source)
        self.assertIn("Running OCR analysis", source)
        self.assertIn("لا ترسل ملفاً آخر حتى تظهر النتيجة", source)

    def test_document_and_photo_use_the_same_canonical_service(self):
        photo_source = (ROOT / "handlers/receipt_processing_policy.py").read_text(encoding="utf-8")
        document_source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
        self.assertIn("handle_receipt_upload", photo_source)
        self.assertIn("handle_receipt_upload", document_source)


if __name__ == "__main__":
    unittest.main()
