"""Regression coverage for canonical payment-method selection during orders."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_order_confirmation_selects_only_canonical_shamcash_methods():
    source = (ROOT / "handlers/order_confirmation_policy.py").read_text(encoding="utf-8")
    assert "code IN ('shamcash_usd', 'shamcash_new_syp')" in source
    assert "enabled = TRUE" in source
    assert "payment_account_snapshot" in source
    assert "payment_qr_photo_id" in source
