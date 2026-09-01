from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_confirmation_requires_the_same_order_as_the_pending_admin_session():
    source = (ROOT / "handlers/admin_order_closure_policy.py").read_text(encoding="utf-8")
    assert "pending_order_id = data.get(\"admin_close_order_id\")" in source
    assert "if pending_order_id != order_id:" in source
    assert "جلسة الإغلاق لا تطابق الطلب المحدد" in source


def test_switching_orders_cannot_reuse_a_previous_order_reason():
    source = (ROOT / "handlers/admin_order_closure_policy.py").read_text(encoding="utf-8")
    assert "previous_order_id = data.get(\"admin_close_order_id\")" in source
    assert "previous_reason = data.get(\"admin_close_reason\") if previous_order_id == order_id else None" in source
