"""Regression coverage for the single effective admin dashboard route."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_payment_methods_router_precedes_legacy_admin_menu_handlers():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    payment_index = source.index("dp.include_router(payment_methods.router)")
    admin_policy_index = source.index("dp.include_router(admin_navigation_policy.router)")
    admin_facade_index = source.index("dp.include_router(admin.router)")
    assert payment_index < admin_policy_index < admin_facade_index


def test_admin_menu_callback_has_one_authoritative_runtime_owner():
    payment_source = (ROOT / "handlers" / "payment_methods.py").read_text(encoding="utf-8")
    assert '@router.callback_query(F.data == "admin_menu")' in payment_source
    assert "enhanced_admin_menu_keyboard" in payment_source
