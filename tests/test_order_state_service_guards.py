import pytest

from services.order_state_service import (
    ALLOWED_TRANSITIONS,
    InvalidOrderTransition,
    transition_order,
)


def test_terminal_states_have_no_outgoing_transitions():
    assert ALLOWED_TRANSITIONS["completed"] == frozenset()
    assert ALLOWED_TRANSITIONS["rejected"] == frozenset()
    assert ALLOWED_TRANSITIONS["expired"] == frozenset()


@pytest.mark.asyncio
async def test_same_status_transition_is_rejected():
    class FakeConn:
        async def fetchrow(self, query, order_id):
            return {"id": order_id, "status": "pending"}

    with pytest.raises(InvalidOrderTransition, match="already pending"):
        await transition_order(FakeConn(), 1, "pending")


@pytest.mark.asyncio
async def test_forward_transition_respects_graph():
    calls = []

    class FakeConn:
        async def fetchrow(self, query, order_id):
            calls.append((query, order_id))
            if "FOR UPDATE" in query:
                return {"id": order_id, "status": "pending", "user_id": 7}
            return {"id": order_id, "status": "waiting_payment"}

        async def execute(self, query, *values):
            calls.append((query, values))

    result = await transition_order(
        FakeConn(),
        1,
        "waiting_payment",
        admin_id=42,
        updates={"approved_at": object(), "payment_deadline": object()},
    )

    assert result["status"] == "waiting_payment"
    assert any("FOR UPDATE" in call[0] for call in calls if isinstance(call[0], str))


@pytest.mark.asyncio
async def test_backward_business_transition_is_rejected():
    class FakeConn:
        async def fetchrow(self, query, order_id):
            return {"id": order_id, "status": "payment_confirmed", "user_id": 7}

    with pytest.raises(InvalidOrderTransition, match="payment_confirmed -> pending"):
        await transition_order(FakeConn(), 1, "pending")


@pytest.mark.asyncio
async def test_unsupported_order_update_field_is_rejected():
    class FakeConn:
        async def fetchrow(self, query, order_id):
            if "FOR UPDATE" in query:
                return {"id": order_id, "status": "pending", "user_id": 7}
            return {"id": order_id, "status": "waiting_payment"}

        async def execute(self, query, *values):
            raise AssertionError("unsupported update must fail before UPDATE")

    with pytest.raises(ValueError, match="Unsupported order update field: wallet_address"):
        await transition_order(
            FakeConn(),
            1,
            "waiting_payment",
            updates={"wallet_address": "not-allowed"},
        )
