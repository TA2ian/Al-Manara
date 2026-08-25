from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_approved_payment_notification_does_not_send_receipt_prompt():
    source = (ROOT / "services/notification_service.py").read_text(encoding="utf-8")
    assert "The approval handler owns the receipt-upload prompt" in source
    assert "After payment, use the receipt-upload button" not in source
    assert "بعد الدفع، أرسل إثبات العملية" not in source


def test_manual_approval_is_the_single_owner_of_receipt_upload_prompt():
    source = (ROOT / "handlers/admin_approval_policy.py").read_text(encoding="utf-8")
    assert "receipt_upload_keyboard(order_id, lang)" in source
    assert "بعد إتمام الدفع للطلب" in source


def test_usd_receipt_review_does_not_label_usd_as_the_syp_exchange_rate():
    source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    assert "if currency == \"NEW.SYP\"" in source
    assert "1 USD = {rate(order.get('exchange_rate'))} NEW.SYP" in source
    assert "سعر الصرف: <b>{rate(order.get('exchange_rate'))}</b> {currency}" not in source


def test_receipt_verification_prefers_immutable_payment_snapshot():
    source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    assert "payment_account_snapshot" in source
    assert "snapshot_account" in source
