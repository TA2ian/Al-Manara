from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_is_configured_for_main_push_and_manual_dispatch():
    source = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "push:" in source
    assert "branches: [main]" in source
    assert "workflow_dispatch:" in source
    assert "pytest -q" in source
    assert "pip check" in source
    assert "compileall -q ." in source


def test_no_replit_runtime_artifacts_remain():
    forbidden = (".replit", "replit.nix", "BUILD_PROMPT.md")
    for name in forbidden:
        assert not (ROOT / name).exists(), name


def test_legacy_compatibility_surface_is_removed():
    for relative_path in (
        "handlers/admin.py",
        "handlers/admin_settings_alias_policy.py",
        "handlers/legacy_wallet_guard.py",
        "services/order_wallet_guard.py",
        "handlers/order.py",
        "handlers/menu.py",
        "handlers/my_orders.py",
        "handlers/verification.py",
        "handlers/verification_pending_guard.py",
        "database_wallet_guards.py",
    ):
        assert not (ROOT / relative_path).exists(), relative_path


def test_canonical_order_constraint_surface_is_active():
    database = (ROOT / "database.py").read_text(encoding="utf-8")
    constraints = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "database_wallet_guards" not in database
    assert "install_order_constraints" in database
    assert "await install_order_constraints(conn)" in database
    assert "order wallet QR does not match the verified saved wallet" in constraints


def test_release_gate_covers_authoritative_services_and_removed_surface():
    source = (ROOT / "tests/test_release_gate.py").read_text(encoding="utf-8")
    assert "handlers.admin_settings_policy" in source
    assert "handlers.verification_policy" in source
    assert "handlers.verification_pending_guard" in source
    assert "services.legal_policy" in source
    assert "services.order_state_service" in source
    assert "services.order_completion_service" in source
    assert "services.receipt_service" in source
    assert "handlers.legacy_wallet_guard" in source
    assert "handlers.my_orders" in source
    assert "handlers.admin" in source
