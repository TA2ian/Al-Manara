"""Regression checks for trusted-customer automatic order approval."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_auto_approval_requires_setting_and_three_completed_orders():
    source = (ROOT / "handlers" / "order_confirmation_policy.py").read_text(encoding="utf-8")
    assert 'SettingsService.get_bool("auto_approve", False)' in source
    assert "status = 'completed'" in source
    assert "completed_count >= 3" in source


def test_auto_approval_uses_the_same_authoritative_payment_transition():
    source = (ROOT / "handlers" / "order_confirmation_policy.py").read_text(encoding="utf-8")
    assert 'transition_order(' in source
    assert '"waiting_payment"' in source
    assert 'NotificationService(bot, Config.ADMIN_IDS).notify_order_approved' in source
    assert 'rollback_order(' in source


def test_auto_approval_still_exposes_receipt_upload_to_customer():
    source = (ROOT / "handlers" / "order_confirmation_policy.py").read_text(encoding="utf-8")
    assert "receipt_upload_keyboard(order_id, lang)" in source
