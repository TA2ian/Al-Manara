from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admin_approval_requires_snapshot_and_rolls_back_if_delivery_fails():
    source = (ROOT / "handlers/admin_approval_policy.py").read_text(encoding="utf-8")
    assert 'order["status"] != "pending"' in source
    assert "payment_account_snapshot" in source
    assert "payment_qr_photo_id" in source
    assert "notify_order_approved" in source
    assert "rollback_order" in source
    assert '"pending"' in source


def test_customer_receipt_flow_supports_image_processing_and_manual_review():
    processing = (ROOT / "handlers/receipt_processing_policy.py").read_text(encoding="utf-8")
    receipt_service = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    document = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    assert "ReceiptStates.waiting_receipt" in processing
    assert "handle_receipt_upload" in processing
    assert "request_manual_receipt_review" in receipt_service
    assert 'order["status"] != "waiting_payment"' in receipt_service
    assert '"receipt_received"' in receipt_service
    assert "is_auto_verified=False" in receipt_service
    assert "ReceiptStates.waiting_receipt" in document


def test_customer_and_admin_notifications_use_the_order_snapshot():
    approval = (ROOT / "handlers/admin_approval_policy.py").read_text(encoding="utf-8")
    payment = (ROOT / "handlers/admin_payment_confirmation_policy.py").read_text(encoding="utf-8")
    completion = (ROOT / "services/order_completion_service.py").read_text(encoding="utf-8")
    assert "payment_account_snapshot" in approval
    assert "payment_qr_photo_id" in approval
    assert "wallet_qr_photo_id" in payment
    assert "wallet_address" in payment
    assert "txid" in completion


def test_receipt_rejection_returns_only_to_waiting_payment():
    source = (ROOT / "handlers/admin_rejection_policy.py").read_text(encoding="utf-8")
    assert 'order["status"] != "receipt_received"' in source
    assert 'transition_order(conn, order_id, "waiting_payment"' in source


def test_active_orders_block_customer_deletion_at_database_boundary():
    source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "prevent_active_order_deletion" in source
    assert "trg_prevent_active_order_deletion" in source
    assert "pending" in source
    assert "waiting_payment" in source
    assert "receipt_received" in source
    assert "payment_confirmed" in source
    assert "active order prevents customer deletion" in source


def test_customer_deletion_path_remains_transactional():
    source = (ROOT / "handlers/admin_user_management_policy.py").read_text(encoding="utf-8")
    assert "async with conn.transaction()" in source
    assert 'DELETE FROM orders WHERE user_id = $1' in source
    assert 'DELETE FROM users WHERE id = $1' in source
