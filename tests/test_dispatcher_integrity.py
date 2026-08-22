import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DispatcherIntegrityTests(unittest.TestCase):
    def test_admin_facade_does_not_nest_directly_registered_rejection_router(self):
        source = Path("handlers/admin.py").read_text(encoding="utf-8")
        self.assertNotIn("admin_rejection_policy", source)

    def test_handlers_package_has_no_legacy_router_side_effects(self):
        source = Path("handlers/__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("from . import order", source)
        self.assertNotIn("from . import admin_rejection_policy", source)

    def test_legacy_order_router_is_not_registered_by_dispatcher(self):
        source = Path("bot.py").read_text(encoding="utf-8")
        self.assertNotIn("dp.include_router(order.router)", source)
        self.assertIn("dp.include_router(order_amount_policy.router)", source)
        self.assertIn("dp.include_router(order_confirmation_policy.router)", source)

    def test_receipt_document_and_photo_paths_are_both_registered(self):
        source = Path("bot.py").read_text(encoding="utf-8")
        self.assertIn("dp.include_router(receipt_processing_policy.router)", source)
        self.assertIn("dp.include_router(receipt_document_policy.router)", source)

    def test_customer_dashboard_entrypoints_are_registered_and_exposed(self):
        bot = Path("bot.py").read_text(encoding="utf-8")
        inline = Path("keyboards/inline.py").read_text(encoding="utf-8")
        reply = Path("keyboards/reply.py").read_text(encoding="utf-8")
        profile = Path("handlers/profile.py").read_text(encoding="utf-8")
        wallets = Path("handlers/wallets.py").read_text(encoding="utf-8")
        orders = Path("handlers/customer_orders_policy.py").read_text(encoding="utf-8")
        settings = Path("handlers/customer_settings_policy.py").read_text(encoding="utf-8")
        navigation = Path("handlers/customer_navigation_policy.py").read_text(encoding="utf-8")

        for router in (
            "profile",
            "wallets",
            "customer_orders_policy",
            "customer_settings_policy",
            "customer_navigation_policy",
        ):
            self.assertIn(f"dp.include_router({router}.router)", bot)

        for callback in ("menu_profile", "menu_wallets", "menu_rate", "menu_help", "menu_disclaimer"):
            self.assertIn(callback, inline)
        self.assertIn("📋 طلباتي", reply)
        self.assertIn('F.data == "menu_profile"', profile)
        self.assertIn('F.data == "menu_wallets"', wallets)
        self.assertIn('F.text.in_(["📋 طلباتي", "📋 Orders"])', orders)
        self.assertIn('F.text.in_({"⚙️ القائمة", "⚙️ Menu", "⚙️ الإعدادات", "⚙️ Settings"})', settings)
        self.assertIn('F.data == "quick_reorder"', navigation)

    def test_customer_dashboard_has_no_legacy_duplicate_navigation_owners(self):
        menu = Path("handlers/menu.py").read_text(encoding="utf-8")
        self.assertNotIn('F.data == "quick_reorder"', menu)
        self.assertNotIn('F.data == "quick_change_lang"', menu)
        self.assertNotIn('F.data == "menu_rate"', menu)
        self.assertNotIn('F.data == "menu_profile"', menu)
        self.assertNotIn('F.data == "menu_wallets"', menu)


if __name__ == "__main__":
    unittest.main()
