def test_admin_ids_accept_both_current_and_legacy_environment_names(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "1001, 1002")
    monkeypatch.setenv("ADMIN_ID", "1003")

    import config

    parsed = config._parse_admin_ids()
    assert parsed == [1001, 1002, 1003]


def test_admin_entry_uses_canonical_access_service():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "handlers" / "admin_entry.py").read_text(encoding="utf-8")
    assert "AdminAccessService" in source
    assert "Config.ADMIN_IDS" not in source


def test_state_processing_lock_cannot_trap_administrator():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "middleware" / "state_processing_lock.py").read_text(encoding="utf-8")
    assert "AdminAccessService.is_admin(user.id)" in source
