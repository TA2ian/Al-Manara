import unittest

from keyboards.inline import order_admin_keyboard


class AdminOrderActionTests(unittest.TestCase):
    def _callbacks(self, status):
        keyboard = order_admin_keyboard(123, status)
        return [button.callback_data for row in keyboard.inline_keyboard for button in row]

    def test_pending_has_approve_and_reject(self):
        callbacks = self._callbacks("pending")
        self.assertIn("admin_approve_123", callbacks)
        self.assertIn("admin_reject_123", callbacks)

    def test_waiting_payment_exposes_reject(self):
        callbacks = self._callbacks("waiting_payment")
        self.assertIn("admin_reject_123", callbacks)

    def test_receipt_received_exposes_receipt_reject_and_order_reject(self):
        callbacks = self._callbacks("receipt_received")
        self.assertIn("admin_reject_receipt_123", callbacks)
        self.assertIn("admin_reject_123", callbacks)


if __name__ == "__main__":
    unittest.main()
