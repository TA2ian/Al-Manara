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


def test_every_admin_dashboard_callback_has_an_authoritative_runtime_owner():
    callback_owners = {
        "admin_pending_orders": "admin_order_list_policy.py",
        "admin_active_orders": "admin_order_list_policy.py",
        "admin_search_order": "admin_navigation_policy.py",
        "admin_dashboard": "admin_navigation_policy.py",
        "admin_analytics": "admin_navigation_policy.py",
        "admin_list_users": "admin_user_management_policy.py",
        "admin_settings": "admin_settings_policy.py",
        "admin_update_rate": "admin_rate_policy.py",
        "admin_broadcast": "admin_broadcast_policy.py",
        "admin_search_user": "admin_search_policy.py",
        "admin_logs": "admin_utility_policy.py",
        "admin_backups": "admin_tools_policy.py",
        "admin_auto_approve": "admin_utility_policy.py",
        "admin_maintenance": "admin_maintenance_policy.py",
        "admin_payment_methods": "payment_method_setup_policy.py",
    }
    keyboard_source = (ROOT / "keyboards" / "inline.py").read_text(encoding="utf-8")
    enhanced_source = (ROOT / "keyboards" / "admin.py").read_text(encoding="utf-8")
    combined_keyboard_source = keyboard_source + "\n" + enhanced_source

    for callback_data, owner in callback_owners.items():
        assert callback_data in combined_keyboard_source, callback_data
        owner_source = (ROOT / "handlers" / owner).read_text(encoding="utf-8")
        assert callback_data in owner_source, f"{callback_data} -> {owner}"


def test_admin_settings_buttons_have_authoritative_handlers():
    keyboard_source = (ROOT / "keyboards" / "inline.py").read_text(encoding="utf-8")
    settings_source = (ROOT / "handlers" / "admin_settings_policy.py").read_text(encoding="utf-8")
    for callback_data in ("setting_fees", "setting_timeout", "setting_limits", "admin_settings"):
        assert callback_data in keyboard_source
        assert callback_data in settings_source
