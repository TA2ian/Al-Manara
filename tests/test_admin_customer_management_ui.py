"""Regression checks for scalable admin customer-management UI."""

import inspect

from handlers import admin_search_policy, admin_user_management_policy


def test_customer_list_has_no_per_row_destructive_actions():
    source = inspect.getsource(admin_user_management_policy._render_user_page)
    assert "admin_del_user_" not in source
    assert "admin_ban_" not in source
    assert "admin_unban_" not in source
    assert 'callback_data="admin_search_user"' in source


def test_customer_search_has_single_match_actions_and_multi_match_guard():
    source = inspect.getsource(admin_search_policy.search_input)
    assert "if len(result_rows) > 1:" in source
    assert "admin_del_user_" not in source
    assert "_customer_action_keyboard" in source


def test_customer_action_keyboard_contains_delete_only_after_search():
    keyboard = admin_search_policy._customer_action_keyboard(123456, False)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "admin_del_user_123456" in callbacks
    assert "admin_ban_123456" in callbacks
