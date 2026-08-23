"""Regression coverage for the two ShamCash admin management surfaces."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_payment_method_account_updates_publish_to_runtime_settings():
    source = (ROOT / "handlers/payment_methods.py").read_text(encoding="utf-8")
    assert "Config.set_shamcash_usd(value)" in source
    assert "Config.set_shamcash_syp(value)" in source
    assert 'SettingsService.set("shamcash_usd", value)' in source
    assert 'SettingsService.set("shamcash_syp", value)' in source


def test_payment_method_panel_remains_the_canonical_persistent_store():
    source = (ROOT / "handlers/payment_methods.py").read_text(encoding="utf-8")
    assert "UPDATE payment_methods SET account_identifier" in source
    assert "UPDATE payment_methods SET qr_photo_id" in source
    assert "UPDATE payment_methods SET enabled = NOT enabled" in source
