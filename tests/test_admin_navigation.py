from pathlib import Path

from keyboards.inline import (
    admin_menu_keyboard,
    order_admin_keyboard,
    order_detail_keyboard,
    order_pagination_keyboard,
    settings_keyboard,
    auto_approve_keyboard,
)
from handlers.verification_admin_policy import (
    _verification_review_keyboard,
    _verification_reject_confirmation_keyboard,
)


def callback_data(keyboard):
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def labels(keyboard):
    return [button.text for row in keyboard.inline_keyboard for button in row]


def test_admin_menu_has_navigation_entry_points():
    data = callback_data(admin_menu_keyboard())
    assert "admin_pending_orders" in data
    assert "admin_active_orders" in data
    assert "admin_settings" in data
    assert "admin_broadcast" in data


def test_verification_review_has_no_admin_exit_button():
    keyboard = _verification_review_keyboard(123)
    data = callback_data(keyboard)
    assert data == ["verify_approve_123", "verify_reject_123"]
    assert "admin_menu" not in data
    assert "🔙 لوحة التحكم" not in labels(keyboard)


def test_verification_rejection_requires_explicit_confirmation():
    keyboard = _verification_reject_confirmation_keyboard(123)
    data = callback_data(keyboard)
    assert "verify_reject_confirm_123" in data
    assert "verify_review_123" in data
    assert "verify_reject_123" not in data
    assert "admin_menu" not in data


def test_order_views_expose_return_to_admin():
    assert "admin_menu" in callback_data(order_detail_keyboard(7))
    assert "admin_menu" in callback_data(order_pagination_keyboard(0, 3, "pending"))
    assert "admin_menu" in callback_data(order_admin_keyboard(7, "pending"))


def test_settings_and_auto_approve_have_back_control():
    data = callback_data(settings_keyboard())
    assert data == ["setting_fees", "setting_timeout", "setting_limits", "admin_menu"]
    assert "setting_rate" not in data
    assert "setting_shamcash_usd" not in data
    assert "setting_shamcash_syp" not in data
    assert "setting_shamcash_name" not in data
    assert "admin_menu" in callback_data(auto_approve_keyboard(False))


def test_order_lifecycle_never_auto_sends_admin_dashboard():
    """The admin dashboard is explicit navigation, never a lifecycle side effect."""
    root = Path(__file__).resolve().parents[1]
    lifecycle_files = (
        "handlers/admin_approval_policy.py",
        "handlers/admin_rejection_policy.py",
        "handlers/admin_payment_confirmation_policy.py",
        "handlers/admin_transfer_policy.py",
        "services/order_completion_service.py",
        "handlers/verification_admin_policy.py",
    )
    forbidden = 'reply_markup=admin_menu_keyboard()'
    for relative_path in lifecycle_files:
        source = (root / relative_path).read_text(encoding="utf-8")
        assert forbidden not in source, f"automatic admin dashboard found in {relative_path}"


def test_lifecycle_handlers_do_not_import_admin_dashboard_for_side_effects():
    root = Path(__file__).resolve().parents[1]
    lifecycle_files = (
        "handlers/admin_approval_policy.py",
        "handlers/admin_rejection_policy.py",
        "handlers/admin_payment_confirmation_policy.py",
        "handlers/admin_transfer_policy.py",
        "services/order_completion_service.py",
        "handlers/verification_admin_policy.py",
    )
    for relative_path in lifecycle_files:
        source = (root / relative_path).read_text(encoding="utf-8")
        assert "from keyboards.inline import admin_menu_keyboard" not in source, relative_path
        assert "from keyboards.inline import (" not in source or "admin_menu_keyboard" not in source, relative_path
