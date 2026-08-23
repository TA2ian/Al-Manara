from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "handlers"


def test_legacy_compatibility_router_is_explicitly_isolated():
    source = (ROOT / "tests/test_router_integrity.py").read_text(encoding="utf-8")
    assert 'LEGACY_COMPATIBILITY_FILES = {"menu.py"}' in source
    assert "Authoritative policy routers" in source


def test_authoritative_dispatch_order_precedes_legacy_compatibility():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "dp.include_router(menu.router)" in source
    assert source.index("dp.include_router(menu.router)") > source.index("dp.include_router(order_amount_policy.router)")
    assert source.index("dp.include_router(menu.router)") > source.index("dp.include_router(verification_pending_guard.router)")


def test_retired_monolithic_order_module_remains_absent():
    assert not (HANDLERS / "order.py").exists()
