from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admin_transfer_requires_payment_confirmation_and_network_valid_txid():
    source = (ROOT / "handlers/admin_transfer_policy.py").read_text(encoding="utf-8")
    assert 'order["status"] != "payment_confirmed"' in source
    assert "_valid_txid" in source
    assert '"TRC20"' in source
    assert '"BEP20"' in source
    assert "complete_order" in source


def test_completion_is_authoritative_and_only_from_payment_confirmed():
    source = (ROOT / "services/order_completion_service.py").read_text(encoding="utf-8")
    assert 'order["status"] != "payment_confirmed"' in source
    assert '"completed"' in source
    assert "transition_order" in source
    assert "txid" in source
    assert "completed_at" in source
    assert '"wallet_qr_photo_id": None' not in source


def test_admin_rejection_has_separate_order_and_receipt_paths():
    source = (ROOT / "handlers/admin_rejection_policy.py").read_text(encoding="utf-8")
    assert "admin_reject_receipt_" in source
    assert "admin_reject_" in source
    assert '"receipt_received"' in source
    assert '"waiting_payment"' in source
    assert '"rejected"' in source
    assert "transition_order" in source


def test_expiry_and_reminders_are_background_order_lifecycle_controls():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "send_expiry_reminders" in source
    assert "check_expired_orders" in source
    assert "payment_deadline" in source
    assert "_track_background_task(check_expired_orders(bot), 'order-expiry-checker')" in source
    assert "_track_background_task(send_expiry_reminders(bot), 'expiry-reminder-worker')" in source
    assert "def _track_background_task(" in source
