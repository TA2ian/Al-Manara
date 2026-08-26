from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admin_entry_points_are_admin_guarded():
    # These are the authoritative admin entry-point policies currently
    # registered by the dispatcher. Do not reference legacy/non-existent
    # modules here: this test is about the actual production routing surface.
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

    admin_start = source.index("def admin_menu_keyboard")
    customer_start = source.index("def main_menu_inline")
    quick_start = source.index("def quick_actions_keyboard")
    assert admin_start != customer_start != quick_start


def test_admin_menu_callback_is_not_a_customer_navigation_target():
    source = (ROOT / "keyboards/inline.py").read_text(encoding="utf-8")
    customer_sections = (
        source[source.index("def main_menu_inline"):source.index("def network_selection_keyboard")],
        source[source.index("def quick_actions_keyboard"):],
    )
    for section in customer_sections:
        assert 'callback_data="admin_menu"' not in section
