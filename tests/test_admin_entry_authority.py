from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_command_has_one_runtime_owner():
    settings = (ROOT / "handlers/admin_settings_policy.py").read_text(encoding="utf-8")
    entry = (ROOT / "handlers/admin_entry.py").read_text(encoding="utf-8")
    assert "@router.message(Command(\"admin\"))" not in settings
    assert "@router.message(Command(\"admin\"))" in entry


def test_settings_policy_contains_only_operational_settings():
    settings = (ROOT / "handlers/admin_settings_policy.py").read_text(encoding="utf-8")
    assert "Command" not in settings
    assert 'callback_data="admin_settings"' in settings
    assert "setting_fees" in settings
    assert "setting_timeout" in settings
    assert "setting_limits" in settings


def test_admin_entry_is_the_only_dashboard_message_owner():
    entry = (ROOT / "handlers/admin_entry.py").read_text(encoding="utf-8")
    assert "reply_markup=admin_menu_keyboard()" in entry
    settings = (ROOT / "handlers/admin_settings_policy.py").read_text(encoding="utf-8")
    assert "Command" not in settings
