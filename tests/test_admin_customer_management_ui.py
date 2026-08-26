"""Regression checks for scalable admin customer-management UI."""

import inspect
from pathlib import Path

from handlers import admin_search_policy, admin_user_management_policy

ROOT = Path(__file__).resolve().parents[1]


def test_customer_list_exposes_confirmed_delete_per_row():
    source = inspect.getsource(admin_user_management_policy._render_user_page)
    assert "admin_del_user_" in source
    assert "callback_data=f\"admin_del_user_{user['telegram_id']}\"" in source
    assert "يمكن حظر أو فك حظر أو حذف أي عميل" in source


def test_customer_list_keeps_blocked_users_reachable_for_unban():
    source = inspect.getsource(admin_user_management_policy._fetch_users)
    render_source = inspect.getsource(admin_user_management_policy._render_user_page)
    assert "WHERE terms_accepted = TRUE" in source
    assert "is_blocked = FALSE" not in source
    assert "admin_unban_" in render_source
    assert "admin_ban_" in render_source


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


def test_customer_delete_handler_requires_confirmation_and_is_transactional():
    source = (ROOT / "handlers/admin_user_management_policy.py").read_text(encoding="utf-8")
    assert 'F.data.startswith("admin_del_user_")' in source
    assert 'F.data.startswith("admin_del_confirm_")' in source
    assert "async with conn.transaction():" in source
    assert "DELETE FROM misconduct_incidents WHERE user_id = $1" in source
    assert "DELETE FROM orders WHERE user_id = $1" in source
    assert "DELETE FROM saved_addresses WHERE user_id = $1" in source
    assert "DELETE FROM users WHERE id = $1" in source
    assert "user_deleted" in source


def test_customer_delete_blocks_active_orders_before_mutation():
    source = (ROOT / "handlers/admin_user_management_policy.py").read_text(encoding="utf-8")
    assert "status IN ('pending','waiting_payment','receipt_received','payment_confirmed')" in source
    assert "لم يتم تطبيق أي جزء من عملية الحذف" in source


def test_customer_mutation_results_do_not_push_a_second_dashboard_message():
    source = (ROOT / "handlers/admin_user_management_policy.py").read_text(encoding="utf-8")
    assert "reply_markup=admin_menu_keyboard()" in source
    assert 'await callback.message.answer("⚙️ لوحة التحكم"' not in source
