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


def test_legacy_compatibility_surface_is_explicit():
    source = (ROOT / "tests/test_router_integrity.py").read_text(encoding="utf-8")
    assert 'LEGACY_COMPATIBILITY_FILES = {"menu.py"}' in source
    assert "test_retired_monolithic_order_handler_is_absent" in source


def test_release_gate_covers_compatibility_guard_and_authoritative_services():
    source = (ROOT / "tests/test_release_gate.py").read_text(encoding="utf-8")
    assert "handlers.legacy_wallet_guard" in source
    assert "services.order_state_service" in source
    assert "services.order_completion_service" in source
    assert "handlers.verification_pending_guard" in source
