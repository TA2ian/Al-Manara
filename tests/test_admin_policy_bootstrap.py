"""Regression tests for incremental admin-router extraction."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_extracted_admin_policies_are_bootstrapped_before_legacy_router():
    bootstrap = (ROOT / "handlers" / "admin_policy_bootstrap.py").read_text(encoding="utf-8")
    assert "admin_order_list_policy.router" in bootstrap
    assert "admin_user_management_policy.router" in bootstrap
    assert "admin.router.include_router(extracted_router)" in bootstrap


def test_handler_package_exposes_extracted_admin_policies():
    init = (ROOT / "handlers" / "__init__.py").read_text(encoding="utf-8")
    assert "admin_order_list_policy" in init
    assert "admin_user_management_policy" in init
    assert "admin_policy_bootstrap" in init


def test_legacy_admin_router_is_still_present_for_unextracted_features():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    admin = (ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
    assert "dp.include_router(admin.router)" in bot
    assert len(admin) > 50000
