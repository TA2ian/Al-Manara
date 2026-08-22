import asyncio
import unittest

from handlers.admin_approval_policy import _sync_customer_status_message


class FakeBot:
    def __init__(self):
        self.calls = []

    async def edit_message_text(self, **kwargs):
        self.calls.append(kwargs)


class CustomerStatusSyncTests(unittest.TestCase):
    def run_async(self, coro):
        return asyncio.run(coro)

    def test_approval_replaces_stale_customer_status(self):
        bot = FakeBot()
        order = {
            "order_number": "ORD_TEST_123",
            "telegram_id": 1001,
            "customer_status_message_id": 77,
            "language": "ar",
        }

        result = self.run_async(_sync_customer_status_message(bot, order, approved=True))

        self.assertTrue(result)
        self.assertEqual(len(bot.calls), 1)
        self.assertEqual(bot.calls[0]["chat_id"], 1001)
        self.assertEqual(bot.calls[0]["message_id"], 77)
        self.assertIn("تمت الموافقة", bot.calls[0]["text"])

    def test_missing_message_id_does_not_break_approval(self):
        bot = FakeBot()
        order = {
            "order_number": "ORD_TEST_123",
            "telegram_id": 1001,
            "customer_status_message_id": None,
            "language": "ar",
        }

        result = self.run_async(_sync_customer_status_message(bot, order, approved=True))

        self.assertFalse(result)
        self.assertEqual(bot.calls, [])


if __name__ == "__main__":
    unittest.main()
