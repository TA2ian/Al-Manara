"""Architecture guard for the cross-worker active-order invariant."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "handlers" / "order_confirmation_policy.py").read_text(encoding="utf-8")


def test_order_confirmation_serializes_same_customer_transactions():
    assert "pg_advisory_xact_lock" in SOURCE
    lock_index = SOURCE.index("pg_advisory_xact_lock")
    active_index = SOURCE.index("status IN ('pending','waiting_payment','receipt_received','payment_confirmed')")
    insert_index = SOURCE.index("INSERT INTO orders")
    assert lock_index < active_index < insert_index
