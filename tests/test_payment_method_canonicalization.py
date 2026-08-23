"""Regression coverage for canonical ShamCash payment-method storage."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_database_migrates_legacy_syp_method_into_canonical_new_syp():
    source = (ROOT / "database.py").read_text(encoding="utf-8")
    assert "code = 'shamcash_syp'" in source
    assert "code = 'shamcash_new_syp'" in source
    assert "DELETE FROM payment_methods WHERE id = $1" in source


def test_database_defines_only_canonical_runtime_payment_method_codes():
    source = (ROOT / "database.py").read_text(encoding="utf-8")
    assert "shamcash_usd" in source
    assert "shamcash_new_syp" in source
    assert "payment_methods WHERE provider = 'ShamCash'" in source
