"""Regression coverage for canonical backup restore behavior."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "handlers/admin_tools_policy.py"


def test_backup_restore_preserves_canonical_payment_methods():
    source = SOURCE.read_text(encoding="utf-8")
    assert '"payment_methods"' in source
    assert "TRUNCATE TABLE users, orders, exchange_rates, audit_logs, blocked_users, feedback_messages, saved_addresses, payment_methods, bot_settings" in source
    assert 'rows = payload["tables"][table]' in source
    assert 'await SettingsService.reload()' in source
    assert "payment_method_legacy_compat" not in source
    assert "handlers.payment_methods" not in source
    assert "ensure_default_methods" not in source


def test_backup_restore_requires_the_canonical_payment_methods_table():
    source = SOURCE.read_text(encoding="utf-8")
    assert "BACKUP_TABLES = (" in source
    assert '    "payment_methods",' in source
    assert 'missing = [table for table in BACKUP_TABLES if table not in tables]' in source


def test_restore_validates_backup_columns_before_interpolating_identifiers():
    source = SOURCE.read_text(encoding="utf-8")
    assert "async def _get_table_columns" in source
    assert "def _validate_restore_rows" in source
    assert "unknown_columns = expected_columns - allowed_columns" in source
    assert "columns != expected_columns" in source
    assert "_validate_restore_rows(tables[table], schemas[table], table)" in source
    assert 'quoted = ", ".join(f\'"{column}"\' for column in columns)' in source


def test_restore_clears_transient_maintenance_notification_jobs():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'await conn.execute("DELETE FROM maintenance_notification_jobs")' in source
