"""Static regression checks for immutable customer and payment-time snapshots."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_database_constraints_snapshot_customer_identity():
    source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "customer_full_name_snapshot" in source
    assert "customer_telegram_id_snapshot" in source
    assert "customer_username_snapshot" in source
    assert "customer_shamcash_account_snapshot" in source
    assert "snapshot_order_customer_identity" in source
    assert "order customer identity snapshot is immutable" in source


def test_database_constraints_protect_payment_deadline():
    source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "protect_order_payment_deadline" in source
    assert "payment deadline is immutable once assigned" in source
    assert "payment deadline cannot precede approval time" in source
    assert "payment deadline cannot precede order creation time" in source
    assert "UPDATE OF payment_deadline, approved_at, created_at, status" in source


def test_order_confirmation_uses_authoritative_server_time():
    source = (ROOT / "handlers" / "order_confirmation_policy.py").read_text(encoding="utf-8")
    assert "from services.time_service import utc_now_naive" in source
    assert "now_utc = utc_now_naive()" in source
    assert "deadline = now_utc + timedelta" in source
    assert "datetime.now(" not in source
    assert "datetime.utcnow(" not in source


def test_expiry_compares_deadline_against_database_now():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "AND o.payment_deadline < NOW()" in source
    assert "transition_order(conn, order['id'], 'expired')" in source
