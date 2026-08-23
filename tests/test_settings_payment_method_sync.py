"""Regression coverage for persistent ShamCash settings synchronization."""
import inspect

from services import settings_service


def test_legacy_shamcash_settings_sync_to_canonical_payment_methods():
    source = inspect.getsource(settings_service)
    assert '"shamcash_usd": ("shamcash_usd", "USD")' in source
    assert '"shamcash_syp": ("shamcash_new_syp", "NEW.SYP")' in source
    assert "UPDATE payment_methods" in source
    assert "account_identifier = $1" in source


def test_settings_are_persisted_before_cache_is_published():
    source = inspect.getsource(settings_service.SettingsService.set)
    assert "async with conn.transaction()" in source
    assert "cls._cache[key] = value" in source
