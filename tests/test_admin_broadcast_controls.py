import html

from handlers.admin_broadcast_policy import (
    MAX_BROADCAST_LENGTH,
    broadcast_preview_keyboard,
    broadcast_start_keyboard,
    is_admin,
)


def test_broadcast_length_limit():
    assert MAX_BROADCAST_LENGTH == 4096
    assert len("x" * MAX_BROADCAST_LENGTH) == MAX_BROADCAST_LENGTH
    assert len("x" * (MAX_BROADCAST_LENGTH + 1)) > MAX_BROADCAST_LENGTH


def test_broadcast_admin_gate(monkeypatch):
    monkeypatch.setattr("handlers.admin_broadcast_policy.Config.ADMIN_IDS", [12345])
    assert is_admin(12345) is True
    assert is_admin(99999) is False


def test_broadcast_preview_escapes_user_content():
    malicious = '<b>send</b> & <script>alert(1)</script>'
    escaped = html.escape(malicious)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped


def test_broadcast_start_requires_explicit_action():
    callback_data = [button.callback_data for row in broadcast_start_keyboard().inline_keyboard for button in row]
    assert "admin_broadcast_cancel" in callback_data
    assert "admin_menu" in callback_data
    assert "admin_broadcast_send" not in callback_data


def test_broadcast_preview_has_send_edit_cancel_and_back():
    callback_data = [button.callback_data for row in broadcast_preview_keyboard().inline_keyboard for button in row]
    assert "admin_broadcast_send" in callback_data
    assert "admin_broadcast_edit" in callback_data
    assert "admin_broadcast_cancel" in callback_data
    assert "admin_menu" in callback_data
