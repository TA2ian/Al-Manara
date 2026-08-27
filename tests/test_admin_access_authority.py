import importlib


def test_admin_ids_accept_both_current_and_legacy_environment_names(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "1001, 1002")
    monkeypatch.setenv("ADMIN_ID", "1003")

    import config

    config = importlib.reload(config)
    assert config.Config.is_admin(1001)
    assert config.Config.is_admin(1002)
    assert config.Config.is_admin(1003)
    assert not config.Config.is_admin(1004)
    assert config.Config.admin_configuration_summary() == "3 administrator ID(s) configured"


def test_admin_entry_uses_canonical_access_service():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "handlers" / "admin_entry.py").read_text(encoding="utf-8")
    assert "AdminAccessService" in source
    assert "Config.ADMIN_IDS" not in source


def test_state_processing_lock_cannot_trap_administrator():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "middleware" / "state_processing_lock.py").read_text(encoding="utf-8")
    assert "AdminAccessService.is_admin(user.id)" in source
