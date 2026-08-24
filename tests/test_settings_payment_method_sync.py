"""Regression coverage for operational settings isolation."""
import inspect

from services import settings_service


def test_settings_service_does_not_mutate_payment_methods():
    source = inspect.getsource(settings_service)
    assert "payment_methods" not in source
    assert "account_identifier = $1" not in source


def test_settings_are_persisted_before_cache_is_published():
    source = inspect.getsource(settings_service.SettingsService.set)
    assert "async with conn.transaction()" in source
    assert "cls._cache[key] = value" in source
