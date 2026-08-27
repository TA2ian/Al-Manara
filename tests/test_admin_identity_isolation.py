from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_entry_uses_current_sender_identity():
    source = (ROOT / "handlers/admin_entry.py").read_text(encoding="utf-8")
    assert "message.from_user" in source
    assert "callback.from_user" in source
    assert "event.from_user" in source
    assert "Config.ADMIN_IDS" not in source
    assert "5702244378" not in source


def test_admin_command_has_single_authoritative_owner():
    matches = []
    for path in (ROOT / "handlers").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if '@router.message(Command("admin"))' in source:
            matches.append(path.name)
    assert matches == ["admin_entry.py"]


def test_admin_entry_does_not_broadcast_or_reuse_recipient_identity():
    source = (ROOT / "handlers/admin_entry.py").read_text(encoding="utf-8")
    forbidden = (
        "bot.send_message(",
        "send_to_all",
        "broadcast",
        "ADMIN_IDS[0]",
        "Config.ADMIN_IDS[0]",
    )
    for token in forbidden:
        assert token not in source, token
