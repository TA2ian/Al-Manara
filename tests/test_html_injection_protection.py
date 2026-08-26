import html
from pathlib import Path

from handlers.order_confirmation_policy import _html as escape_order_value
from services.notification_service import _html as escape_notification_value


ROOT = Path(__file__).resolve().parents[1]


def test_dynamic_html_values_are_escaped():
    payload = '<a href="https://evil.example">ادفع هنا</a> & <b>مزيف</b>'
    expected = html.escape(payload, quote=True)

    assert escape_order_value(payload) == expected
    assert escape_notification_value(payload) == expected
    assert "<a href=" not in escape_order_value(payload)
    assert "<b>مزيف</b>" not in escape_notification_value(payload)


def test_order_admin_notification_uses_escape_boundary():
    source = (ROOT / "handlers/order_confirmation_policy.py").read_text(encoding="utf-8")

    assert "import html" in source
    assert "def _html(value: object)" in source
    assert "_html(customer_name)" in source
    assert "_html(username)" in source
    assert "_html(customer_shamcash)" in source
    assert "_html(wallet['address'])" in source


def test_notification_service_uses_escape_boundary_for_user_content():
    source = (ROOT / "services/notification_service.py").read_text(encoding="utf-8")

    assert "import html" in source
    assert "def _html(value: object)" in source
    assert "_html(username)" in source
    assert "_html(text or 'بدون نص')" in source
    assert "_html(order.get('order_number', 'N/A'))" in source
    assert "_html(order.get('username', 'N/A'))" in source
    assert "safe_recipient = _html(recipient)" in source
    assert "safe_address = _html(address)" in source


def test_admin_message_template_escapes_broadcast_body_and_recipient():
    source = (ROOT / "services/admin_message_service.py").read_text(encoding="utf-8")

    assert "safe_body = html.escape(clean_body)" in source
    assert "html.escape(recipient_name.strip())" in source
