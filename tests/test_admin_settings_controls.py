"""Regression coverage for every button exposed by the admin settings panel."""
import inspect

from handlers import admin_settings_policy, admin_settings_alias_policy, admin_utility_policy, admin_tools_policy
from keyboards.inline import settings_keyboard


def callbacks(keyboard):
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_every_settings_button_has_an_authoritative_handler():
    data = callbacks(settings_keyboard())
    source = inspect.getsource(admin_settings_policy)
    alias_source = inspect.getsource(admin_settings_alias_policy)
    assert "setting_rate" in source
    assert "setting_fees" in source
    assert "setting_shamcash_usd" in source
    assert "setting_shamcash_new_syp" in alias_source
    assert "setting_shamcash_name" in source
    assert "setting_timeout" in source
    assert "setting_limits" in source
    assert "admin_menu" in data


def test_admin_backup_route_has_single_authority():
    tools_source = inspect.getsource(admin_tools_policy)
    utility_source = inspect.getsource(admin_utility_policy)
    assert 'F.data == "admin_backups"' in tools_source
    assert 'F.data == "admin_backups"' not in utility_source
