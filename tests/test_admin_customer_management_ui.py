"""Regression checks for scalable admin customer-management UI."""

from handlers import admin_search_policy, admin_user_management_policy


def test_customer_list_has_no_per_row_destructive_actions():
    keyboard = admin_user_management_policy._user_action_keyboard(123456, False)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "admin_del_user_123456" in callbacks

    # The customer list renderer must not embed destructive actions per row.
    source = admin_user_management_policy._render_user_page.__code__.co_consts
    assert not any("admin_del_user_" in str(value) for value in source)
    assert not any("admin_ban_" in str(value) for value in source)


def test_search_policy_exposes_customer_actions_only_on_single_match():
    source = admin_search_policy.search_input.__code__.co_consts
    constants = "\n".join(str(value) for value in source)
    assert "admin_del_user_" in constants or "_customer_action_keyboard" in admin_search_policy.__dict__
    assert "بحث عميل آخر" in constants
