"""Regression checks for atomic payment-deadline expiry."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_expiry_uses_order_state_service():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from services.order_state_service import transition_order, InvalidOrderTransition" in source
    assert "transition_order(conn, order['id'], 'expired')" in source
    assert "UPDATE orders SET status = 'expired'" not in source


def test_expiry_only_processes_waiting_payment_orders():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "WHERE o.status = 'waiting_payment'" in source
    assert "AND o.payment_deadline < NOW()" in source
