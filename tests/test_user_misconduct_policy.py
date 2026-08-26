import asyncio
from datetime import datetime, timedelta

from services.user_misconduct_service import (
    MAX_CONFIRMED_INCIDENTS,
    MisconductDecision,
    confirm_manipulation,
    customer_notice,
    suspension_notice,
)


class FakeConnection:
    def __init__(self, incident_count: int):
        self.incident_count = incident_count
        self.executed = []

    async def fetchrow(self, query, *args):
        if "SELECT id, telegram_id, is_blocked FROM users" in query:
            return {"id": 10, "telegram_id": 123456, "is_blocked": False}
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def fetchval(self, query, *args):
        if "SELECT COUNT(*) FROM misconduct_incidents" in query:
            return self.incident_count
        raise AssertionError(f"Unexpected fetchval query: {query}")

    async def execute(self, query, *args):
        self.executed.append((query, args))


def test_first_confirmed_incident_creates_four_hour_suspension():
    conn = FakeConnection(0)
    decision = asyncio.run(
        confirm_manipulation(
            conn,
            user_id=10,
            telegram_id=123456,
            order_id=100,
            admin_id=900,
        )
    )

    assert decision.incident_number == 1
    assert decision.suspension_expires_at is not None
    assert timedelta(hours=3, minutes=59) < decision.suspension_expires_at - datetime.utcnow() <= timedelta(hours=4)
    assert decision.requires_admin_review is False
    assert decision.final_warning is False


def test_second_confirmed_incident_creates_twenty_four_hour_review_suspension():
    conn = FakeConnection(1)
    decision = asyncio.run(
        confirm_manipulation(
            conn,
            user_id=10,
            telegram_id=123456,
            order_id=101,
            admin_id=900,
        )
    )

    assert decision.incident_number == 2
    assert decision.suspension_expires_at is not None
    assert timedelta(hours=23, minutes=59) < decision.suspension_expires_at - datetime.utcnow() <= timedelta(hours=24)
    assert decision.requires_admin_review is True
    assert decision.final_warning is False


def test_third_confirmed_incident_is_indefinite_final_review():
    conn = FakeConnection(2)
    decision = asyncio.run(
        confirm_manipulation(
            conn,
            user_id=10,
            telegram_id=123456,
            order_id=102,
            admin_id=900,
        )
    )

    assert decision.incident_number == MAX_CONFIRMED_INCIDENTS
    assert decision.suspension_expires_at is None
    assert decision.requires_admin_review is True
    assert decision.final_warning is True


def test_customer_notice_marks_third_incident_as_final_warning():
    decision = MisconductDecision(
        incident_number=3,
        suspension_expires_at=None,
        requires_admin_review=True,
        final_warning=True,
    )

    notice = customer_notice(decision, "ar")
    assert "الفرصة الأخيرة" in notice
    assert "معلق" in notice


def test_temporary_suspension_notice_does_not_expose_internal_reason():
    notice = suspension_notice(
        "confirmed manipulation: 4-hour service suspension",
        datetime.utcnow() + timedelta(hours=2),
        "ar",
    )
    assert "الخدمة معلقة مؤقتاً" in notice
    assert "confirmed manipulation" not in notice
