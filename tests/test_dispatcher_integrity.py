import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DispatcherIntegrityTests(unittest.TestCase):
    def test_admin_policies_are_registered_directly(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        for router in (
            "admin_order_list_policy",
            "admin_user_management_policy",
            "admin_utility_policy",
            "admin_maintenance_policy",
            "admin_settings_policy",
        ):
            self.assertIn(f"dp.include_router({router}.router)", source)
        self.assertNotIn("dp.include_router(admin.router)", source)
        self.assertFalse((ROOT / "handlers/admin.py").exists())

    def test_handlers_package_has_no_legacy_router_side_effects(self):
        source = (ROOT / "handlers/__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("from . import order", source)
        self.assertNotIn("from . import admin_rejection_policy", source)

    def test_legacy_order_router_is_not_registered_by_dispatcher(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertNotIn("dp.include_router(order.router)", source)
        self.assertIn("dp.include_router(order_amount_policy.router)", source)
        self.assertIn("dp.include_router(order_confirmation_policy.router)", source)

    def test_receipt_document_and_photo_paths_are_both_registered(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("dp.include_router(receipt_processing_policy.router)", source)
        self.assertIn("dp.include_router(receipt_document_policy.router)", source)

    def test_customer_dashboard_entrypoints_are_registered_and_exposed(self):
        bot = (ROOT / "bot.py").read_text(encoding="utf-8")
        inline = (ROOT / "keyboards/inline.py").read_text(encoding="utf-8")
        reply = (ROOT / "keyboards/reply.py").read_text(encoding="utf-8")
        profile = (ROOT / "handlers/profile.py").read_text(encoding="utf-8")
        wallets = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
        orders = (ROOT / "handlers/customer_orders_policy.py").read_text(encoding="utf-8")
        settings = (ROOT / "handlers/customer_settings_policy.py").read_text(encoding="utf-8")
        navigation = (ROOT / "handlers/customer_navigation_policy.py").read_text(encoding="utf-8")

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
        for label in ("⚙️ القائمة", "⚙️ Menu", "⚙️ الإعدادات", "⚙️ Settings"):
            self.assertIn(label, settings)
        self.assertIn("_normalize_menu_label", settings)
        self.assertIn('F.data == "quick_reorder"', navigation)

    def test_customer_navigation_has_single_authority(self):
        source = (ROOT / "handlers/customer_navigation_policy.py").read_text(encoding="utf-8")
        self.assertIn('F.data == "quick_reorder"', source)
        self.assertIn('F.data == "menu_help"', source)
        self.assertIn('F.data == "menu_disclaimer"', source)
        self.assertIn('F.data == "quick_saved_addresses"', source)
        self.assertIn('F.data.startswith("view_addr_")', source)
        self.assertIn('F.data.startswith("del_addr_")', source)
        self.assertFalse((ROOT / "handlers/menu.py").exists())


if __name__ == "__main__":
    unittest.main()
