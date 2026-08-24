"""Regression coverage for every button exposed by the operational settings panel."""
import inspect
from pathlib import Path

from handlers import admin_settings_policy, admin_utility_policy, admin_tools_policy, admin_rate_policy, payment_method_setup_policy
from keyboards.inline import settings_keyboard


ROOT = Path(__file__).resolve().parents[1]


def callbacks(keyboard):
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_every_settings_button_has_an_authoritative_handler():
    data = callbacks(settings_keyboard())
    settings_source = inspect.getsource(admin_settings_policy)
    rate_source = inspect.getsource(admin_rate_policy)
    payment_source = inspect.getsource(payment_method_setup_policy)

    assert "setting_fees" in settings_source
    assert "setting_timeout" in settings_source
    assert "setting_limits" in settings_source
    assert "setting_rate" not in settings_source
    assert "setting_rate" in rate_source
    assert "admin_payment_methods" in payment_source
    assert "setting_shamcash_usd" not in data
    assert "setting_shamcash_syp" not in data
    assert "setting_shamcash_name" not in data
    assert "admin_menu" in data
    assert not (ROOT / "handlers/admin_settings_alias_policy.py").exists()


def test_admin_backup_route_has_single_authority():
    tools_source = inspect.getsource(admin_tools_policy)
    utility_source = inspect.getsource(admin_utility_policy)
    assert 'F.data == "admin_backups"' in tools_source
    assert 'F.data == "admin_backups"' not in utility_source
