import html
import unittest

from handlers.admin_broadcast_policy import MAX_BROADCAST_LENGTH, is_admin


class AdminBroadcastPolicyTests(unittest.TestCase):
    def test_broadcast_length_limit(self):
        self.assertEqual(MAX_BROADCAST_LENGTH, 4096)
        self.assertEqual(len("x" * MAX_BROADCAST_LENGTH), MAX_BROADCAST_LENGTH)
        self.assertGreater(len("x" * (MAX_BROADCAST_LENGTH + 1)), MAX_BROADCAST_LENGTH)

    def test_broadcast_admin_gate(self):
        original = list(is_admin.__globals__["Config"].ADMIN_IDS)
        try:
            is_admin.__globals__["Config"].ADMIN_IDS = [12345]
            self.assertTrue(is_admin(12345))
            self.assertFalse(is_admin(99999))
        finally:
            is_admin.__globals__["Config"].ADMIN_IDS = original

    def test_broadcast_preview_is_html_escaped(self):
        malicious = '<b>send</b> & <script>alert(1)</script>'
        escaped = html.escape(malicious)
        self.assertNotIn("<script>", escaped)
        self.assertIn("&lt;script&gt;", escaped)


if __name__ == "__main__":
    unittest.main()
