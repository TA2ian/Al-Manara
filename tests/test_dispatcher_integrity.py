import unittest
from pathlib import Path


class DispatcherIntegrityTests(unittest.TestCase):
    def test_admin_facade_does_not_nest_directly_registered_rejection_router(self):
        source = Path("handlers/admin.py").read_text(encoding="utf-8")
        self.assertNotIn("admin_rejection_policy", source)

    def test_legacy_order_router_is_not_registered_by_dispatcher(self):
        source = Path("bot.py").read_text(encoding="utf-8")
        self.assertNotIn("dp.include_router(order.router)", source)
        self.assertIn("dp.include_router(order_amount_policy.router)", source)
        self.assertIn("dp.include_router(order_confirmation_policy.router)", source)

    def test_receipt_document_and_photo_paths_are_both_registered(self):
        source = Path("bot.py").read_text(encoding="utf-8")
        self.assertIn("dp.include_router(receipt_processing_policy.router)", source)
        self.assertIn("dp.include_router(receipt_document_policy.router)", source)


if __name__ == "__main__":
    unittest.main()
