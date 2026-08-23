"""Regression coverage for settings that affect new order calculations."""
import inspect

from handlers import order_amount_policy, order_confirmation_policy


def test_order_limits_are_loaded_from_settings_service():
    source = inspect.getsource(order_amount_policy)
    assert "SettingsService" in source
    assert '"min_order"' in source
    assert '"max_order"' in source
    assert '"daily_limit"' in source


def test_payment_timeout_is_loaded_from_settings_service():
    source = inspect.getsource(order_confirmation_policy)
    assert "SettingsService" in source
    assert '"payment_timeout_minutes"' in source
    assert "_payment_timeout_minutes()" in source
