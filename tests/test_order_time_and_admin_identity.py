"""Regression checks for authoritative order time and admin identity context."""

import inspect

from handlers import admin_approval_policy, order_confirmation_policy
from services import notification_service, order_completion_service


def test_order_timestamp_source_is_server_utc_not_local_naive_clock():
    source = inspect.getsource(order_confirmation_policy)
    assert "utc_now_naive" in source
    assert "datetime.now()" not in source
    assert "datetime.utcnow()" not in source


def test_admin_approval_timestamp_source_is_server_utc():
    source = inspect.getsource(admin_approval_policy)
    assert "utc_now_naive" in source
    assert "datetime.now()" not in source
    assert "datetime.utcnow()" not in source


def test_completion_timestamp_source_is_server_utc():
    source = inspect.getsource(order_completion_service.complete_order)
    assert "utc_now_naive" in source
    assert "datetime.now()" not in source
    assert "datetime.utcnow()" not in source


def test_completion_closes_ephemeral_bot_session():
    source = inspect.getsource(order_completion_service.complete_order)
    assert "bot.session.close()" in source
    assert "finally:" in source


def test_customer_deadline_message_uses_operational_duration_policy():
    source = inspect.getsource(notification_service.NotificationService.notify_order_approved)
    assert "OperationalPolicyService.get_payment_timeout_minutes" in source
    assert "deadline.strftime" not in source
    assert "format_order_datetime" not in source
    assert "لديك <b>{deadline_minutes} دقيقة</b>" in source


def test_admin_approval_displays_duration_not_geographic_clock_time():
    source = inspect.getsource(admin_approval_policy.approve_order_authoritative)
    assert "OperationalPolicyService.get_payment_timeout_minutes" in source
    assert "format_order_datetime" not in source
    assert "المهلة المحددة: <b>{timeout_minutes} دقيقة</b> من لحظة اعتماد الطلب" in source


def test_admin_approval_contains_customer_identity_and_shamcash_context():
    source = inspect.getsource(admin_approval_policy.approve_order_authoritative)
    assert "u.full_name" in source
    assert "u.telegram_id" in source
    assert "u.shamcash_account" in source
    assert "ShamCash العميل" in source
    assert "payment_recipient_name_snapshot" in source
    assert "payment_account_snapshot" in source


def test_order_confirmation_requires_verified_customer_identity_context():
    source = inspect.getsource(order_confirmation_policy.confirm_order_authoritative)
    assert "full_name, username, shamcash_account" in source
    assert "بيانات حسابك غير مكتملة" in source


def test_receipt_review_prefers_order_customer_snapshots_and_repairs_legacy_rows():
    source = inspect.getsource(__import__("services.receipt_service", fromlist=["notify_admins_receipt"]).notify_admins_receipt)
    assert "customer_full_name_snapshot" in source
    assert "customer_telegram_id_snapshot" in source
    assert "customer_username_snapshot" in source
    assert "customer_shamcash_account_snapshot" in source
    assert "SELECT telegram_id, full_name, username, shamcash_account FROM users WHERE id = $1" in source
    assert "N/A" in source
