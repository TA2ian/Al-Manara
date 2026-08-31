import asyncio
import unittest
from contextlib import asynccontextmanager
from datetime import datetime

from services.order_state_service import InvalidOrderTransition, rollback_order, transition_order


class FakeConn:
    def __init__(self, status="pending", in_transaction=False):
        self.order = {
            "id": 7,
            "user_id": 42,
            "status": status,
            "created_at": datetime.now(),
        }
        self.executed = []
        self.transaction_events = []
        self._in_transaction = in_transaction

    def is_in_transaction(self):
        return self._in_transaction

    @asynccontextmanager
    async def transaction(self):
        self.transaction_events.append("begin")
        previous = self._in_transaction
        self._in_transaction = True
        try:
            yield
        except Exception:
            self.transaction_events.append("rollback")
            raise
        else:
            self.transaction_events.append("commit")
        finally:
            self._in_transaction = previous

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        if "FOR UPDATE" in query:
            return dict(self.order)
        if "SELECT * FROM orders" in query:
            return dict(self.order)
        return None

    async def execute(self, query, *args):
        self.executed.append(("execute", query, args))
        if query.startswith("UPDATE orders SET"):
            self.order["status"] = args[0]
        return "OK"


class OrderStateServiceTests(unittest.TestCase):
    def run_async(self, coro):
        return asyncio.run(coro)

    def test_valid_transition_is_atomic_and_audited(self):
        conn = FakeConn("pending")
        result = self.run_async(transition_order(conn, 7, "waiting_payment", admin_id=99))
        self.assertEqual(result["status"], "waiting_payment")
        audit_calls = [call for call in conn.executed if call[0] == "execute" and "INSERT INTO audit_logs" in call[1]]
        self.assertEqual(len(audit_calls), 1)
        self.assertEqual(audit_calls[0][2][1], 99)
        self.assertEqual(audit_calls[0][2][4], "pending")
        self.assertEqual(audit_calls[0][2][5], "waiting_payment")
        self.assertEqual(conn.transaction_events, ["begin", "commit"])

    def test_transition_reuses_existing_transaction(self):
        conn = FakeConn("pending", in_transaction=True)
        result = self.run_async(transition_order(conn, 7, "waiting_payment", admin_id=99))
        self.assertEqual(result["status"], "waiting_payment")
        self.assertEqual(conn.transaction_events, [])
        self.assertTrue(conn.is_in_transaction())

    def test_valid_transition_honors_expected_guards(self):
        conn = FakeConn("payment_confirmed")
        conn.order.update({"network": "TRC20", "wallet_address": "TRECIPIENT", "amount_usdt": 25})
        result = self.run_async(
            transition_order(
                conn,
                7,
                "completed",
                admin_id=99,
                expected={"network": "trc20", "wallet_address": "trecipient", "amount_usdt": 25},
            )
        )
        self.assertEqual(result["status"], "completed")

    def test_guard_mismatch_is_rejected_atomically(self):
        conn = FakeConn("payment_confirmed")
        conn.order.update({"network": "TRC20", "wallet_address": "TRECIPIENT", "amount_usdt": 25})
        with self.assertRaises(InvalidOrderTransition):
            self.run_async(
                transition_order(
                    conn,
                    7,
                    "completed",
                    admin_id=99,
                    expected={"amount_usdt": 30},
                )
            )
        self.assertEqual(conn.transaction_events, ["begin", "rollback"])

    def test_admin_can_reject_pending_order(self):
        conn = FakeConn("pending")
        result = self.run_async(transition_order(conn, 7, "rejected", admin_id=99))
        self.assertEqual(result["status"], "rejected")

    def test_admin_can_reject_waiting_payment_order(self):
        conn = FakeConn("waiting_payment")
        result = self.run_async(transition_order(conn, 7, "rejected", admin_id=99))
        self.assertEqual(result["status"], "rejected")

    def test_admin_can_reject_receipt_received_order(self):
        conn = FakeConn("receipt_received")
        result = self.run_async(transition_order(conn, 7, "rejected", admin_id=99))
        self.assertEqual(result["status"], "rejected")

    def test_delivery_rollback_is_explicit_and_audited(self):
        conn = FakeConn("waiting_payment")
        result = self.run_async(
            rollback_order(
                conn,
                7,
                "pending",
                admin_id=99,
                updates={"approved_at": None, "payment_deadline": None},
            )
        )
        self.assertEqual(result["status"], "pending")
        audit_calls = [call for call in conn.executed if call[0] == "execute" and "INSERT INTO audit_logs" in call[1]]
        self.assertEqual(audit_calls[-1][2][2], "order_status_rollback")
        self.assertEqual(conn.transaction_events, ["begin", "commit"])

    def test_rollback_rejects_wrong_source_state(self):
        conn = FakeConn("receipt_received")
        with self.assertRaises(InvalidOrderTransition):
            self.run_async(rollback_order(conn, 7, "pending", admin_id=99))
        self.assertEqual(conn.transaction_events, ["begin", "rollback"])

    def test_invalid_transition_is_rejected(self):
        conn = FakeConn("pending")
        with self.assertRaises(InvalidOrderTransition):
            self.run_async(transition_order(conn, 7, "completed", admin_id=99))
        self.assertEqual(conn.transaction_events, ["begin", "rollback"])

    def test_duplicate_transition_is_rejected(self):
        conn = FakeConn("waiting_payment")
        with self.assertRaises(InvalidOrderTransition):
            self.run_async(transition_order(conn, 7, "waiting_payment", admin_id=99))
        self.assertEqual(conn.transaction_events, ["begin", "rollback"])

    def test_terminal_order_cannot_be_reopened(self):
        conn = FakeConn("completed")
        with self.assertRaises(InvalidOrderTransition):
            self.run_async(transition_order(conn, 7, "waiting_payment", admin_id=99))
        self.assertEqual(conn.transaction_events, ["begin", "rollback"])


if __name__ == "__main__":
    unittest.main()
