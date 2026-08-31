from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_receipt_submission_constraint_is_installed():
    source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION protect_receipt_submission()" in source
    assert "receipt submission is not allowed for this order state" in source
    assert "trg_protect_receipt_submission" in source


def test_receipt_submission_constraint_allows_waiting_payment_and_receipt_received():
    source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "OLD.status <> 'waiting_payment'" in source
    assert "NEW.status <> 'receipt_received'" in source
