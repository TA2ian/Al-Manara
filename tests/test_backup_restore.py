import unittest

from handlers.admin_tools_policy import _restore_value


class BackupRestoreTests(unittest.TestCase):
    def test_boolean_strings_restore_to_real_booleans(self):
        self.assertIs(_restore_value("true", "boolean"), True)
        self.assertIs(_restore_value("false", "boolean"), False)
        self.assertIs(_restore_value("1", "boolean"), True)
        self.assertIs(_restore_value("0", "boolean"), False)

    def test_integer_and_numeric_restore_types(self):
        self.assertEqual(_restore_value("42", "integer"), 42)
        self.assertEqual(str(_restore_value("12.50", "numeric")), "12.50")


if __name__ == "__main__":
    unittest.main()
