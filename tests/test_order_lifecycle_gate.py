import unittest

from services.order_lifecycle import (
    ACTIVE_ORDER_STATUSES,
    TERMINAL_ORDER_STATUSES,
    is_active_order_status,
    is_terminal_order_status,
)


class OrderLifecycleGateTests(unittest.TestCase):
    def test_rejected_order_is_terminal_and_does_not_block_new_order(self):
        self.assertFalse(is_active_order_status("rejected"))
        self.assertTrue(is_terminal_order_status("rejected"))
        self.assertNotIn("rejected", ACTIVE_ORDER_STATUSES)
        self.assertIn("rejected", TERMINAL_ORDER_STATUSES)

    def test_expired_order_is_terminal_and_does_not_block_new_order(self):
        self.assertFalse(is_active_order_status("expired"))
        self.assertTrue(is_terminal_order_status("expired"))

    def test_receipt_received_order_still_blocks_new_order(self):
        self.assertTrue(is_active_order_status("receipt_received"))
        self.assertFalse(is_terminal_order_status("receipt_received"))

    def test_payment_confirmed_order_still_blocks_new_order(self):
        self.assertTrue(is_active_order_status("payment_confirmed"))
        self.assertFalse(is_terminal_order_status("payment_confirmed"))


if __name__ == "__main__":
    unittest.main()
