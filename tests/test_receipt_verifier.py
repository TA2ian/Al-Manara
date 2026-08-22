import unittest

from services.receipt_verifier import ReceiptVerifier


class ReceiptVerifierTests(unittest.TestCase):
    def test_masked_account_prefix_or_suffix_match(self):
        self.assertTrue(ReceiptVerifier._compare_masked_account("4264****", "426412345678"))
        self.assertTrue(ReceiptVerifier._compare_masked_account("****5678", "426412345678"))
        self.assertFalse(ReceiptVerifier._compare_masked_account("9999****", "426412345678"))

    def test_date_matching_supports_both_common_orders(self):
        self.assertTrue(ReceiptVerifier._date_matches("2026-08-22", "2026-08-22"))
        self.assertTrue(ReceiptVerifier._date_matches("22/08/2026", "2026-08-22"))
        self.assertFalse(ReceiptVerifier._date_matches("21/08/2026", "2026-08-22"))

    def test_amount_message_path_does_not_raise_for_missing_amount(self):
        fields = ReceiptVerifier._extract_shamcash_fields("المبلغ: 0")
        self.assertEqual(fields["amount"], 0.0)


if __name__ == "__main__":
    unittest.main()
