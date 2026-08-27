"""Regression coverage for canonical payment methods after restore."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backup_restore_preserves_canonical_payment_methods():
    source = (ROOT / "handlers/admin_tools_policy.py").read_text(encoding="utf-8")
    assert '"payment_methods"' in source
    assert "TRUNCATE TABLE users, orders, exchange_rates, audit_logs, blocked_users, feedback_messages, saved_addresses, payment_methods, bot_settings" in source
    assert 'rows = payload["tables"][table]' in source
    assert 'await SettingsService.reload()' in source
    assert "payment_method_legacy_compat" not in source
    assert "handlers.payment_methods" not in source
    assert "ensure_default_methods" not in source


def test_backup_restore_requires_the_canonical_payment_methods_table():
    source = (ROOT / "handlers/admin_tools_policy.py").read_text(encoding="utf-8")
    assert "BACKUP_TABLES = (" in source
    assert '    "payment_methods",' in source
    assert 'missing = [table for table in BACKUP_TABLES if table not in payload.get("tables", {})]' in source
