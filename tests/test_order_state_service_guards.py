from contextlib import asynccontextmanager

import pytest

from services.order_state_service import (
    ALLOWED_TRANSITIONS,
    InvalidOrderTransition,
    rollback_order,
    transition_order,
)


class TransactionalFakeConn:
    def __init__(self, status="pending"):
        self.status = status
        self.calls = []
        self.update_count = 0

    @asynccontextmanager
    async def transaction(self):
        self.calls.append("transaction_enter")
        try:
            yield
        except Exception:
            self.calls.append("transaction_rollback")
            raise
        else:
            self.calls.append("transaction_commit")

    async def fetchrow(self, query, order_id):
        self.calls.append((query, order_id))
        if "FOR UPDATE" in query:
            return {"id": order_id, "status": self.status, "user_id": 7}
        return {"id": order_id, "status": self.status}

    async def execute(self, query, *values):
        self.calls.append((query, values))
        if query.startswith("UPDATE orders SET"):
            self.update_count += 1
            self.status = values[0]


def test_terminal_states_have_no_outgoing_transitions():
    assert ALLOWED_TRANSITIONS["completed"] == frozenset()
    assert ALLOWED_TRANSITIONS["rejected"] == frozenset()
    assert ALLOWED_TRANSITIONS["expired"] == frozenset()


@pytest.mark.asyncio
async def test_same_status_transition_is_rejected_inside_transaction():
    conn = TransactionalFakeConn(status="pending")

    with pytest.raises(InvalidOrderTransition, match="already pending"):
        await transition_order(conn, 1, "pending")

    assert conn.update_count == 0
    assert conn.calls[-1] == "transaction_rollback"


@pytest.mark.asyncio
async def test_forward_transition_respects_graph_and_commits_transaction():
    conn = TransactionalFakeConn(status="pending")

    result = await transition_order(
        conn,
        1,
        "waiting_payment",
        admin_id=42,
        updates={"approved_at": object(), "payment_deadline": object()},
    )

    assert result["status"] == "waiting_payment"
    assert conn.update_count == 1
    assert "transaction_commit" in conn.calls
    assert any("FOR UPDATE" in call[0] for call in conn.calls if isinstance(call, tuple) and isinstance(call[0], str))


@pytest.mark.asyncio
async def test_backward_business_transition_is_rejected():
    conn = TransactionalFakeConn(status="payment_confirmed")

    with pytest.raises(InvalidOrderTransition, match="payment_confirmed -> pending"):
        await transition_order(conn, 1, "pending")

    assert conn.update_count == 0
    assert conn.calls[-1] == "transaction_rollback"


@pytest.mark.asyncio
async def test_unsupported_order_update_field_is_rejected_before_update():
    conn = TransactionalFakeConn(status="pending")

    with pytest.raises(ValueError, match="Unsupported order update field: wallet_address"):
        await transition_order(
            conn,
            1,
            "waiting_payment",
            updates={"wallet_address": "not-allowed"},
        )

    assert conn.update_count == 0
    assert conn.calls[-1] == "transaction_rollback"


@pytest.mark.asyncio
async def test_rollback_allows_only_waiting_payment_to_pending():
    conn = TransactionalFakeConn(status="waiting_payment")

    result = await rollback_order(
        conn,
        1,
        "pending",
        updates={"approved_at": None, "payment_deadline": None},
    )

    assert result["status"] == "pending"
    assert conn.update_count == 1
    assert "transaction_commit" in conn.calls


@pytest.mark.asyncio
async def test_rollback_rejects_other_source_states():
    conn = TransactionalFakeConn(status="receipt_received")

    with pytest.raises(InvalidOrderTransition, match="Invalid rollback from receipt_received"):
        await rollback_order(conn, 1, "pending")

    assert conn.update_count == 0
    assert conn.calls[-1] == "transaction_rollback"


@pytest.mark.asyncio
async def test_unknown_rollback_target_is_rejected_before_database_access():
    conn = TransactionalFakeConn(status="waiting_payment")

    with pytest.raises(InvalidOrderTransition, match="Unsupported rollback target"):
        await rollback_order(conn, 1, "receipt_received")

    assert conn.calls == []
