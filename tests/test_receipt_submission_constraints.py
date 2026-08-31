from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")


def test_receipt_submission_constraint_is_installed():
    source = _source()
    assert "CREATE OR REPLACE FUNCTION protect_receipt_submission()" in source
    assert "receipt submission is not allowed for this order state" in source
    assert "trg_protect_receipt_submission" in source


def test_receipt_submission_constraint_allows_waiting_payment_and_receipt_received():
    source = _source()
    assert "IF OLD.status <> 'waiting_payment'" in source
    assert "NEW.receipt_upload_count <= OLD.receipt_upload_count" in source


def test_receipt_submission_requires_a_real_new_attempt():
    source = _source()
    assert "NEW.receipt_upload_count IS NULL OR NEW.receipt_upload_count <= OLD.receipt_upload_count" in source
    assert "NEW.receipt_photo_id IS NULL OR btrim(NEW.receipt_photo_id) = ''" in source
    assert "NEW.receipt_upload_count > 3" in source


def test_receipt_submission_trigger_does_not_run_as_a_status_mutation_gate():
    source = _source()
    assert "BEFORE UPDATE OF receipt_photo_id, receipt_upload_count ON orders" in source
    assert "BEFORE UPDATE OF receipt_photo_id, receipt_upload_count, status" not in source
