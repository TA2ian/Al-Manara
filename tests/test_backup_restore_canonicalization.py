"""Regression coverage for canonical payment methods after restore."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backup_restore_recanonicalizes_payment_methods():
    source = (ROOT / "handlers/admin_tools_policy.py").read_text(encoding="utf-8")
    assert "from handlers.payment_methods import ensure_default_methods" in source
    assert "await ensure_default_methods(conn)" in source
    assert "توحيد وسائل ShamCash إلى USD وNEW.SYP" in source
