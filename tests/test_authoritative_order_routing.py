import unittest
from pathlib import Path


class AuthoritativeOrderRoutingTests(unittest.TestCase):
    def test_active_order_delegates_to_authoritative_amount_flow(self):
        source = Path("handlers/active_order_policy.py").read_text(encoding="utf-8")
        self.assertIn("from handlers.order_amount_policy import start_order_authoritative", source)
        self.assertNotIn("from handlers.order import start_order", source)

    def test_dispatcher_registers_rejection_before_runtime_use(self):
        source = Path("bot.py").read_text(encoding="utf-8")
        self.assertIn("admin_rejection_policy", source)
        self.assertIn("dp.include_router(admin_rejection_policy.router)", source)


if __name__ == "__main__":
    unittest.main()
