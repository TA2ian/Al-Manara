import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _function_source(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"Function {function_name!r} was not found")


def test_admin_entry_points_are_admin_guarded():
    for relative_path in (
        "handlers/admin_tools_policy.py",
        "handlers/admin_settings_policy.py",
        "handlers/admin_approval_policy.py",
        "handlers/admin_rejection_policy.py",
        "handlers/admin_payment_confirmation_policy.py",
        "handlers/admin_transfer_policy.py",
        "handlers/verification_admin_policy.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "Config.ADMIN_IDS" in source, relative_path
        assert "Access denied" in source, relative_path


def test_admin_and_customer_keyboards_are_separate_definitions():
    source = (ROOT / "keyboards/inline.py").read_text(encoding="utf-8")
    assert "def admin_menu_keyboard" in source
    assert "def main_menu_inline" in source
    assert "def quick_actions_keyboard" in source

    tree = ast.parse(source)
    functions = {
        node.name: node.lineno
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert functions["admin_menu_keyboard"] != functions["main_menu_inline"]
    assert functions["main_menu_inline"] != functions["quick_actions_keyboard"]
    assert functions["admin_menu_keyboard"] != functions["quick_actions_keyboard"]


def test_admin_menu_callback_is_not_a_customer_navigation_target():
    source = (ROOT / "keyboards/inline.py").read_text(encoding="utf-8")
    main_menu = _function_source(source, "main_menu_inline")
    quick_actions = _function_source(source, "quick_actions_keyboard")
    assert 'callback_data="admin_menu"' not in main_menu
    assert 'callback_data="admin_menu"' not in quick_actions
