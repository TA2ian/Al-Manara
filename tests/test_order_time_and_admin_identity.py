"""Regression checks for authoritative order time and admin identity context."""

from datetime import datetime
import inspect

from handlers import admin_approval_policy, order_confirmation_policy
from services import notification_service, time_service


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


def test_payment_deadline_is_rendered_through_canonical_time_service():
    source = inspect.getsource(notification_service.NotificationService.notify_order_approved)
    assert "format_order_datetime" in source
    assert "deadline.strftime" not in source


def test_business_time_conversion_is_deterministic():
    value = datetime(2026, 8, 26, 9, 49)
    assert time_service.format_order_datetime(value) == "2026-08-26 12:49"


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
