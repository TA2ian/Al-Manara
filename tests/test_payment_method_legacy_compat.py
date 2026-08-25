from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_payment_method_callback_aliases_are_supported():
    source = (ROOT / "handlers/payment_method_legacy_compat.py").read_text(encoding="utf-8")
    assert '"USD": "shamcash_usd"' in source
    assert '"NEW.SYP": "shamcash_new_syp"' in source
    assert "admin_pm_(?:enable|disable|toggle)_" in source
    assert "_canonicalize_legacy_callback" in source


def test_legacy_callbacks_delegate_to_canonical_state_transition():
    source = (ROOT / "handlers/payment_method_legacy_compat.py").read_text(encoding="utf-8")
    assert "_set_payment_method_enabled" in source
    assert "payment_method_enable_legacy_callback" in source
    assert "payment_method_disable_legacy_callback" in source
    assert "payment_method_toggle_legacy_callback" in source


def test_legacy_router_is_registered_before_canonical_payment_router():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    legacy = source.index("dp.include_router(payment_method_legacy_compat.router)")
    canonical = source.index("dp.include_router(payment_method_setup_policy.router)")
    assert legacy < canonical
