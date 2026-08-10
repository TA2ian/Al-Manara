import asyncio
import unittest
from datetime import datetime

from services.order_state_service import InvalidOrderTransition, transition_order


class FakeConn:
    def __init__(self, status="pending"):
        self.order = {
            "id": 7,
            "user_id": 42,
            "status": status,
            "created_at": datetime.now(),
        }
        self.executed = []

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
        result = self.run_async(
            transition_order(conn, 7, "waiting_payment", admin_id=99)
        )
        self.assertEqual(result["status"], "waiting_payment")
        audit_calls = [
            call for call in conn.executed
            if call[0] == "execute" and "INSERT INTO audit_logs" in call[1]
        ]
        self.assertEqual(len(audit_calls), 1)
        self.assertEqual(audit_calls[0][2][1], 99)
        self.assertEqual(audit_calls[0][2][4], "pending")
        self.assertEqual(audit_calls[0][2][5], "waiting_payment")

    def test_invalid_transition_is_rejected(self):
        conn = FakeConn("pending")
        with self.assertRaises(InvalidOrderTransition):
            self.run_async(transition_order(conn, 7, "completed", admin_id=99))

    def test_duplicate_transition_is_rejected(self):
        conn = FakeConn("waiting_payment")
        with self.assertRaises(InvalidOrderTransition):
            self.run_async(transition_order(conn, 7, "waiting_payment", admin_id=99))

    def test_terminal_order_cannot_be_reopened(self):
        conn = FakeConn("completed")
        with self.assertRaises(InvalidOrderTransition):
            self.run_async(transition_order(conn, 7, "waiting_payment", admin_id=99))


if __name__ == "__main__":
    unittest.main()
