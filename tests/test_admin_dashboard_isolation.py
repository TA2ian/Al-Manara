from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FLOW_HANDLERS = (
    "handlers/admin_approval_policy.py",
    "handlers/admin_rejection_policy.py",
    "handlers/admin_payment_confirmation_policy.py",
    "handlers/admin_transfer_policy.py",
    "handlers/verification_admin_policy.py",
)


def test_admin_dashboard_is_not_auto_sent_during_flow_handlers():
    for relative_path in FLOW_HANDLERS:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "reply_markup=admin_menu_keyboard()" not in source, relative_path
        assert "reply_markup=admin_menu_keyboard (" not in source, relative_path
        assert '"⚙️ <b>لوحة التحكم</b>"' not in source, relative_path
        assert '"⚙️ <b>Admin Dashboard</b>"' not in source, relative_path
        assert 'await callback.message.answer("⚙️ لوحة التحكم"' not in source, relative_path


def test_dashboard_keyboard_is_only_a_controlled_navigation_target():
    source = (ROOT / "keyboards/inline.py").read_text(encoding="utf-8")
    assert 'callback_data="admin_menu"' in source


def test_admin_entry_owns_dashboard_message_creation():
    entry = (ROOT / "handlers/admin_entry.py").read_text(encoding="utf-8")
    assert "reply_markup=enhanced_admin_menu_keyboard()" in entry
    assert "reply_markup=admin_menu_keyboard()" not in entry
