from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backup_covers_operational_tables_and_versioned_format():
    source = (ROOT / "handlers/admin_tools_policy.py").read_text(encoding="utf-8")
    for table in ("users", "orders", "exchange_rates", "audit_logs", "blocked_users", "feedback_messages", "saved_addresses", "payment_methods", "bot_settings"):
        assert f'"{table}"' in source
    assert '"format": "al-manara-backup"' in source
    assert "BACKUP_VERSION" in source


def test_restore_validates_before_replacing_data_and_uses_one_transaction():
    source = (ROOT / "handlers/admin_tools_policy.py").read_text(encoding="utf-8")
    assert 'payload.get("format") != "al-manara-backup"' in source
    assert 'payload.get("version") != BACKUP_VERSION' in source
    assert "async with conn.transaction():" in source
    assert "TRUNCATE TABLE users, orders" in source
    assert "await SettingsService.reload()" in source


def test_restore_rejects_unsupported_scalar_values():
    source = (ROOT / "handlers/admin_tools_policy.py").read_text(encoding="utf-8")
    assert "Invalid boolean backup value" in source
    assert "datetime.fromisoformat" in source
    assert "Decimal(str(value))" in source
