import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_HANDLERS = (
    "handlers/admin_approval_policy.py",
    "handlers/admin_rejection_policy.py",
    "handlers/admin_payment_confirmation_policy.py",
    "handlers/admin_transfer_policy.py",
    "handlers/verification_admin_policy.py",
)


def _flow_function_sources(source: str) -> list[str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    excluded = {"confirm_manipulation_callback"}
    return [
        "\n".join(lines[node.lineno - 1:node.end_lineno])
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name not in excluded
    ]


def test_admin_dashboard_is_not_auto_sent_during_flow_handlers():
    for relative_path in FLOW_HANDLERS:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        for function_source in _flow_function_sources(source):
            assert "reply_markup=admin_menu_keyboard()" not in function_source, relative_path
            assert "reply_markup=admin_menu_keyboard (" not in function_source, relative_path
            assert '"⚙️ <b>لوحة التحكم</b>"' not in function_source, relative_path
            assert '"⚙️ <b>Admin Dashboard</b>"' not in function_source, relative_path
            assert 'await callback.message.answer("⚙️ لوحة التحكم"' not in function_source, relative_path


def test_dashboard_keyboard_is_only_a_controlled_navigation_target():
    source = (ROOT / "keyboards/inline.py").read_text(encoding="utf-8")
    assert 'callback_data="admin_menu"' in source


def test_admin_entry_owns_dashboard_message_creation():
    entry = (ROOT / "handlers/admin_entry.py").read_text(encoding="utf-8")
    assert "reply_markup=enhanced_admin_menu_keyboard()" in entry
    assert "reply_markup=admin_menu_keyboard()" not in entry
