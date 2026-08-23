from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "handlers"


def test_legacy_customer_menu_is_absent():
    assert not (HANDLERS / "menu.py").exists()


def test_legacy_admin_facade_is_absent():
    assert not (HANDLERS / "admin.py").exists()
    assert not (HANDLERS / "admin_settings_alias_policy.py").exists()


def test_retired_order_wallet_qr_guard_is_absent():
    assert not (HANDLERS / "legacy_wallet_guard.py").exists()
    states = (ROOT / "states.py").read_text(encoding="utf-8")
    assert "waiting_wallet_qr" not in states


def test_customer_navigation_is_single_authority():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    navigation = (HANDLERS / "customer_navigation_policy.py").read_text(encoding="utf-8")
    assert "dp.include_router(customer_navigation_policy.router)" in source
    for callback in ("menu_help", "menu_disclaimer", "quick_contact", "quick_saved_addresses", "view_addr_", "del_addr_"):
        assert callback in navigation


def test_retired_monolithic_order_module_remains_absent():
    assert not (HANDLERS / "order.py").exists()
