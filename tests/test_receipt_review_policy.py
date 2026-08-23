import unittest

from services.receipt_service import _customer_result_message


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


if __name__ == "__main__":
    unittest.main()
