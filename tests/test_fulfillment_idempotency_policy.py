from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fulfillment_claim_service_uses_durable_database_ownership():
    source = (ROOT / "services/fulfillment_claim_service.py").read_text(encoding="utf-8")
    assert "order_fulfillment_claims" in source
    assert "PRIMARY KEY REFERENCES orders(id)" in source
    assert "FOR UPDATE" in source
    assert "owned_by_other_admin" in source
    assert "released_at" in source


def test_admin_transfer_claims_before_external_transfer():
    source = (ROOT / "handlers/admin_transfer_policy.py").read_text(encoding="utf-8")
    assert "claim_order_fulfillment" in source
    assert "owned_by_other_admin" in source
    assert "تم حجز تنفيذ هذا التحويل لك" in source
    assert "لا تنفذ التحويل الخارجي أكثر من مرة" in source


def test_cancel_releases_fulfillment_claim_without_changing_order_state():
    source = (ROOT / "handlers/admin_transfer_policy.py").read_text(encoding="utf-8")
    assert "release_order_fulfillment" in source
    assert "تم إلغاء حجز التحويل" in source


def test_completion_requires_claim_owner_and_finalizes_claim_with_order():
    source = (ROOT / "services/order_completion_service.py").read_text(encoding="utf-8")
    assert "order_fulfillment_claims" in source
    assert "released_at" in source
    assert "completed_at" in source
    assert "admin_id" in source
    assert "transition_order" in source


def test_completion_signature_requires_admin_identity():
    source = (ROOT / "services/order_completion_service.py").read_text(encoding="utf-8")
    assert "async def complete_order(msg, state, txid: str, screenshot_id: str, order_id: int, admin_id: int)" in source
