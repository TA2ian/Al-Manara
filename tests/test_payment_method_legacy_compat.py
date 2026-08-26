from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_payment_method_callback_aliases_are_supported():
    source = (ROOT / "handlers/payment_method_legacy_compat.py").read_text(encoding="utf-8")
    assert '"USD": "shamcash_usd"' in source
    assert '"usd": "shamcash_usd"' in source
    assert '"shamcash_USD": "shamcash_usd"' in source
    assert '"NEW.SYP": "shamcash_new_syp"' in source
    assert '"new.syp": "shamcash_new_syp"' in source
    assert '"shamcash_syp": "shamcash_new_syp"' in source
    assert '"shamcash_new.syp": "shamcash_new_syp"' in source
    assert "_LEGACY_CODE_PATTERN" in source
    assert "_canonicalize_legacy_callback" in source


def test_legacy_compatibility_surface_excludes_canonical_and_future_codes():
    source = (ROOT / "handlers/payment_method_legacy_compat.py").read_text(encoding="utf-8")
    assert '"shamcash_usd": "shamcash_usd"' not in source
    assert '"shamcash_new_syp": "shamcash_new_syp"' not in source
    assert "[^\\s]+" not in source
    assert "(?!confirm$)" not in source


def test_legacy_callbacks_delegate_to_canonical_handlers_and_state_transition():
    source = (ROOT / "handlers/payment_method_legacy_compat.py").read_text(encoding="utf-8")
    assert "_set_payment_method_enabled" in source
    assert "payment_method_enable_legacy_callback" in source
    assert "payment_method_disable_legacy_callback" in source
    assert "payment_method_toggle_legacy_callback" in source
    assert "payment_method_view" in source
    assert "payment_method_setup_start" in source
    assert "_delegate_with_canonical_data" in source


def test_canonical_payment_router_is_registered_before_legacy_compat_router():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    canonical = source.index("dp.include_router(payment_method_setup_policy.router)")
    legacy = source.index("dp.include_router(payment_method_legacy_compat.router)")
    assert canonical < legacy
