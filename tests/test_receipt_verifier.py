import unittest

from services.receipt_verifier import ReceiptVerifier


class ReceiptVerifierTests(unittest.TestCase):
    def test_masked_account_prefix_or_suffix_match(self):
        self.assertTrue(ReceiptVerifier._compare_masked_account("4264****", "426412345678"))
        self.assertTrue(ReceiptVerifier._compare_masked_account("****5678", "426412345678"))
        self.assertFalse(ReceiptVerifier._compare_masked_account("9999****", "426412345678"))

    def test_masked_account_supports_arabic_indic_digits(self):
        self.assertTrue(ReceiptVerifier._compare_masked_account("٤٢٦٤****", "426412345678"))

    def test_date_matching_supports_both_common_orders_and_arabic_digits(self):
        self.assertTrue(ReceiptVerifier._date_matches("2026-08-22", "2026-08-22"))
        self.assertTrue(ReceiptVerifier._date_matches("22/08/2026", "2026-08-22"))
        self.assertTrue(ReceiptVerifier._date_matches("٢٢/٠٨/٢٠٢٦", "2026-08-22"))
        self.assertFalse(ReceiptVerifier._date_matches("21/08/2026", "2026-08-22"))

    def test_amount_extraction_supports_arabic_indic_digits(self):
        self.assertIn(125.50, ReceiptVerifier._extract_amounts("المبلغ: ١٢٥٫٥٠ SYP"))

    def test_shamcash_fields_support_common_label_variants(self):
        fields = ReceiptVerifier._extract_shamcash_fields(
            """التاريخ: 22/08/2026
اسم المرسل: Grey
حساب المرسل: 4264****
اسم المستفيد: Al Manara
حساب المستفيد: 1234****
المبلغ: 125.50 SYP"""
        )
        self.assertEqual(fields["date"], "22/08/2026")
        self.assertEqual(fields["sender_name"], "Grey")
        self.assertEqual(fields["sender_account"], "4264****")
        self.assertEqual(fields["recipient_name"], "Al Manara")
        self.assertEqual(fields["recipient_account"], "1234****")
        self.assertEqual(fields["amount"], 125.50)

    def test_missing_amount_remains_zero_without_arbitrary_numeric_fallback(self):
        fields = ReceiptVerifier._extract_shamcash_fields("رقم العملية: 123456\nالتاريخ: 22/08/2026")
        self.assertEqual(fields["amount"], 0.0)

    def test_amount_message_path_does_not_raise_for_missing_amount(self):
        fields = ReceiptVerifier._extract_shamcash_fields("المبلغ: 0")
        self.assertEqual(fields["amount"], 0.0)


if __name__ == "__main__":
    unittest.main()
