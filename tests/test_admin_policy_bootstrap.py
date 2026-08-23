"""Regression tests for the authoritative decomposed admin-router stack."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_facade_and_alias_modules_are_removed():
    assert not (ROOT / "handlers" / "admin.py").exists()
    assert not (ROOT / "handlers" / "admin_settings_alias_policy.py").exists()


def test_authoritative_admin_policies_are_registered_directly():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    for marker in (
        "admin_order_list_policy.router",
        "admin_user_management_policy.router",
        "admin_utility_policy.router",
        "admin_maintenance_policy.router",
        "admin_settings_policy.router",
        "admin_rejection_policy.router",
        "admin_broadcast_policy.router",
        "admin_rate_policy.router",
        "admin_navigation_policy.router",
        "admin_approval_policy.router",
        "admin_payment_confirmation_policy.router",
        "admin_transfer_policy.router",
        "admin_note_policy.router",
    ):
        assert marker in bot


def test_removed_financial_dashboard_module_is_not_referenced():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    navigation = (ROOT / "handlers" / "admin_navigation_policy.py").read_text(encoding="utf-8")

    assert not (ROOT / "handlers" / "admin_financial_dashboard_policy.py").exists()
    assert "admin_financial_dashboard_policy" not in bot
    assert 'F.data == "admin_dashboard"' in navigation
    assert 'F.data == "admin_analytics"' in navigation


def test_handler_package_initializer_is_side_effect_free():
    init = (ROOT / "handlers" / "__init__.py").read_text(encoding="utf-8")
    assert "from . import order" not in init
    assert "from . import admin_rejection_policy" not in init
