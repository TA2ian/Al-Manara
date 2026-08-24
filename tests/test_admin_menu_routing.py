"""Regression coverage for the single effective admin dashboard route."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_payment_method_router_is_registered_directly_without_the_retired_module():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "dp.include_router(payment_method_setup_policy.router)" in source
    assert "payment_methods.router" not in source


def test_admin_router_graph_has_no_retired_facade():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "from handlers import (" in source
    assert "admin," not in source
    assert "dp.include_router(admin.router)" not in source
    assert not (ROOT / "handlers/admin.py").exists()


def test_admin_policies_are_registered_directly():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    for router_name in (
        "admin_order_list_policy",
        "admin_user_management_policy",
        "admin_utility_policy",
        "admin_maintenance_policy",
        "admin_settings_policy",
    ):
        assert f"dp.include_router({router_name}.router)" in source


def test_admin_dashboard_and_payment_methods_have_single_owners():
    entry_source = (ROOT / "handlers" / "admin_entry.py").read_text(encoding="utf-8")
    payment_source = (ROOT / "handlers" / "payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert "enhanced_admin_menu_keyboard" in entry_source
    assert '@router.callback_query(F.data == "admin_menu")' in entry_source
    assert '@router.callback_query(F.data == "admin_payment_methods")' in payment_source
    assert '@router.callback_query(F.data == "admin_menu")' not in payment_source
