"""Regression checks for receipt submission versus payment-deadline races."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_database_receipt_constraints_protect_the_submission_window():
    source = (ROOT / "database_receipt_retry_constraints.py").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION protect_receipt_submission_window()" in source
    assert "NEW.status = 'waiting_payment'" in source
    assert "NEW.payment_deadline > CURRENT_TIMESTAMP" in source
    assert "OLD.status = 'waiting_payment'" in source
    assert "NEW.status = 'receipt_received'" in source
    assert "receipt submission is not allowed outside the active payment window" in source


def test_expired_orders_cannot_receive_direct_receipt_mutations():
    source = (ROOT / "database_receipt_retry_constraints.py").read_text(encoding="utf-8")
    assert "trg_protect_receipt_submission_window" in source
    assert "BEFORE UPDATE OF receipt_photo_id, receipt_upload_count, status, payment_deadline" in source
    assert "RAISE EXCEPTION 'receipt submission is not allowed outside the active payment window'" in source
