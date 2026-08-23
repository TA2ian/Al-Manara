from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_customer_search_is_admin_only_and_supports_operational_identifiers():
    source = (ROOT / "handlers/admin_tools_policy.py").read_text(encoding="utf-8")
    assert 'callback.from_user.id' in source
    for value in ("Telegram ID", "@username", "رقم الهاتف", "اسم العميل", "ShamCash"):
        assert value in source


def test_internal_order_notes_are_persisted_and_audited():
    source = (ROOT / "handlers/admin_note_policy.py").read_text(encoding="utf-8")
    assert "admin_notes" in source
    assert "INSERT INTO audit_logs" in source
    assert "admin_id" in source
    assert "الملاحظة داخلية" in source


def test_backup_does_not_store_environment_secrets():
    source = (ROOT / "handlers/admin_tools_policy.py").read_text(encoding="utf-8")
    assert "لا تتضمن أسرار البيئة" in source
    assert "BOT_TOKEN" not in source
    assert "DATABASE_URL" not in source
