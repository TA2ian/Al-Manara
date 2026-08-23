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
    assert "payment_methods WHERE provider = 'ShamCash'" in source or "WHERE provider = 'ShamCash'" in source


def test_order_payment_snapshot_authority_is_the_canonical_database_constraints_module():
    database_source = (ROOT / "database.py").read_text(encoding="utf-8")
    constraints_source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "database_wallet_guards" not in database_source
    assert "from database_order_constraints import install_order_constraints" in database_source
    assert "await install_order_constraints(conn)" in database_source
    assert "snapshot_order_payment_method" in constraints_source
    assert "code IN ('shamcash_usd', 'shamcash_new_syp')" in constraints_source
    assert "payment_account_snapshot" in constraints_source
    assert "payment_qr_photo_id" in constraints_source
    assert "BEFORE INSERT ON orders" in constraints_source
