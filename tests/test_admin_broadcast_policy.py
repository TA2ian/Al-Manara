import pytest

from handlers.admin_broadcast_policy import MAX_BROADCAST_LENGTH, is_admin


def test_broadcast_length_limit():
    assert MAX_BROADCAST_LENGTH == 4096
    assert len("x" * MAX_BROADCAST_LENGTH) == MAX_BROADCAST_LENGTH
    assert len("x" * (MAX_BROADCAST_LENGTH + 1)) > MAX_BROADCAST_LENGTH


def test_broadcast_admin_gate(monkeypatch):
    monkeypatch.setattr("handlers.admin_broadcast_policy.Config.ADMIN_IDS", [12345])
    assert is_admin(12345) is True
    assert is_admin(99999) is False


def test_broadcast_preview_is_html_escaped():
    import html

    malicious = '<b>send</b> & <script>alert(1)</script>'
    escaped = html.escape(malicious)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
