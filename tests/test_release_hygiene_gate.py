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


def test_removed_runtime_compatibility_surfaces_stay_removed():
    forbidden_paths = (
        "handlers/admin.py",
        "handlers/admin_settings_alias_policy.py",
        "handlers/legacy_wallet_guard.py",
        "handlers/wallet_qr_first_policy.py",
        "handlers/order_wallet_qr_policy.py",
        "handlers/verification.py",
        "handlers/verification_pending_guard.py",
        "handlers/verification_keyboard_cleanup.py",
        "handlers/payment_methods.py",
        "handlers/payment_method_legacy_compat.py",
        "handlers/menu.py",
        "handlers/my_orders.py",
        "handlers/order.py",
        "services/order_wallet_guard.py",
        "database_wallet_guards.py",
        "tests/test_payment_method_legacy_compat.py",
    )
    for relative_path in forbidden_paths:
        assert not (ROOT / relative_path).exists(), relative_path


def test_payment_method_runtime_has_one_current_owner():
    bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
    canonical_source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    keyboard_source = (ROOT / "keyboards/inline.py").read_text(encoding="utf-8")

    assert "payment_method_setup_policy" in bot_source
    assert "payment_method_callback_policy" not in bot_source
    assert "payment_method_legacy_compat" not in bot_source
    assert "admin_pm_account_" not in bot_source
    assert "admin_pm_qr_" not in bot_source
    assert "admin_pm_account_" not in canonical_source
    assert "admin_pm_qr_" not in canonical_source
    assert "payment_methods_keyboard" not in keyboard_source
    assert "payment_method_actions" not in keyboard_source


def test_canonical_order_constraint_surface_is_active():
    database = (ROOT / "database.py").read_text(encoding="utf-8")
    constraints = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "database_wallet_guards" not in database
    assert "install_order_constraints" in database
    assert "await install_order_constraints(conn)" in database
    assert "order wallet QR does not match the verified saved wallet" in constraints


def test_release_gate_tracks_only_live_router_modules():
    source = (ROOT / "tests/test_release_gate.py").read_text(encoding="utf-8")
    assert "handlers.admin_settings_policy" in source
    assert "handlers.verification_policy" in source
    assert "handlers.verification_pending_policy" in source
    assert "handlers.legacy_wallet_guard" not in source
    assert "handlers.my_orders" not in source
    assert "handlers.admin" not in source


def test_dispatcher_does_not_reference_retired_compatibility_routers():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    forbidden = (
        "legacy_wallet_guard",
        "wallet_qr_first_policy",
        "order_wallet_qr_policy",
        "verification_pending_guard",
        "verification_keyboard_cleanup",
        "payment_method_legacy_compat",
        "admin_settings_alias_policy",
        "handlers.admin",
    )
    for token in forbidden:
        assert token not in source
