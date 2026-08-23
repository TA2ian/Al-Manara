from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_order_state_graph_is_authoritative_and_terminal_states_are_closed():
    source = (ROOT / "services/order_state_service.py").read_text(encoding="utf-8")
    assert '"pending": frozenset({"waiting_payment", "rejected", "expired"})' in source
    assert '"waiting_payment": frozenset({"receipt_received", "rejected", "expired"})' in source
    assert '"receipt_received": frozenset({"waiting_payment", "payment_confirmed", "rejected"})' in source
    assert '"payment_confirmed": frozenset({"completed"})' in source
    assert '"completed": frozenset()' in source
    assert '"rejected": frozenset()' in source
    assert '"expired": frozenset()' in source
    assert "FOR UPDATE" in source
    assert "audit_logs" in source


def test_database_state_guard_matches_service_and_supports_compensating_rollback():
    source = (ROOT / "database.py").read_text(encoding="utf-8")
    assert "OLD.status='waiting_payment' AND NEW.status IN ('receipt_received','rejected','expired','pending')" in source
    assert "OLD.status='payment_confirmed' AND NEW.status IN ('completed')" in source
    assert "OLD.status='payment_confirmed' AND NEW.status IN ('completed','expired')" not in source
    assert "INSERT INTO audit_logs" not in source[source.index("CREATE OR REPLACE FUNCTION enforce_order_state_transition()"):source.index("CREATE TRIGGER trg_enforce_order_state_transition")]


def test_payment_confirmation_uses_authoritative_transition_service():
    source = (ROOT / "handlers/admin_payment_confirmation_policy.py").read_text(encoding="utf-8")
    assert "transition_order" in source
    assert '"payment_confirmed"' in source
    assert "InvalidOrderTransition" in source
    assert 'order["status"] != "receipt_received"' in source


def test_receipt_manual_review_cannot_bypass_waiting_payment():
    source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    assert "async def request_manual_receipt_review" in source
    assert 'order["status"] != "waiting_payment"' in source
    assert '"receipt_received"' in source
    assert "transition_order" in source
    assert "is_auto_verified=False" in source


def test_receipt_verification_never_completes_payment_by_itself():
    verifier = (ROOT / "services/receipt_verifier.py").read_text(encoding="utf-8")
    receipt_service = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    assert "auto_verified" in verifier
    assert "payment_confirmed" not in verifier
    assert "transition_order" in receipt_service
    assert '"receipt_received"' in receipt_service


def test_payment_snapshot_and_new_syp_contract_are_present():
    source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "payment_account_snapshot" in source
    assert "payment_qr_photo_id" in source
    assert "NEW.SYP" in source
    assert "enabled" in source


def test_central_numeric_formatters_exist_for_all_financial_classes():
    source = (ROOT / "services/formatters.py").read_text(encoding="utf-8")
    for function_name in ("usdt", "money", "rate", "percent"):
        assert f"def {function_name}(" in source
    assert "ROUND_HALF_UP" in source


def test_expiry_worker_uses_authoritative_transition():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "transition_order" in source
    assert '"expired"' in source
    assert "payment_deadline" in source


def test_order_confirmation_snapshots_verified_wallet_and_payment_data():
    source = (ROOT / "handlers/order_confirmation_policy.py").read_text(encoding="utf-8")
    assert "verification_status = 'verified'" in source
    assert "qr_photo_id IS NOT NULL" in source
    assert "payment_account_snapshot" in source
    assert "payment_qr_photo_id" in source
    assert "wallet[\"address\"]" in source
    assert "wallet[\"qr_photo_id\"]" in source
