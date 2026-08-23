"""Regression coverage for the single effective admin dashboard route."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_payment_methods_router_precedes_admin_navigation():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    payment_index = source.index("dp.include_router(payment_methods.router)")
    admin_policy_index = source.index("dp.include_router(admin_navigation_policy.router)")
    assert payment_index < admin_policy_index


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


def test_admin_menu_callback_has_one_authoritative_runtime_owner():
    payment_source = (ROOT / "handlers" / "payment_methods.py").read_text(encoding="utf-8")
    assert '@router.callback_query(F.data == "admin_menu")' in payment_source
    assert "enhanced_admin_menu_keyboard" in payment_source
