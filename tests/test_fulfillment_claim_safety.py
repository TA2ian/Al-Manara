from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_fulfillment_claim_is_persistent_and_one_per_order():
    source = _read("services/order_fulfillment_claim.py")
    assert "order_fulfillment_claims" in source
    assert "order_id INTEGER PRIMARY KEY" in source
    assert "admin_id BIGINT NOT NULL" in source
    assert "INSERT INTO order_fulfillment_claims" in source


def test_fulfillment_claim_schema_is_installed_at_database_initialization():
    database_source = _read("database.py")
    claim_source = _read("services/order_fulfillment_claim.py")
    assert "from services.order_fulfillment_claim import install_fulfillment_claim_schema" in database_source
    assert "await install_fulfillment_claim_schema(conn)" in database_source
    assert "async def install_fulfillment_claim_schema(conn)" in claim_source


def test_claim_read_and_mutation_paths_do_not_run_schema_ddl():
    source = _read("services/order_fulfillment_claim.py")
    install_body = source.split("async def install_fulfillment_claim_schema", 1)[1]
    runtime_source = source.split("async def get_fulfillment_claim", 1)[1]
    assert "await conn.execute(CLAIM_TABLE_SQL)" in install_body
    assert "await install_fulfillment_claim_schema" not in runtime_source
    assert "CREATE TABLE IF NOT EXISTS" not in runtime_source


def test_transfer_flow_claims_before_external_transfer_instructions():
    source = _read("handlers/admin_transfer_policy.py")
    assert "claim_order_fulfillment" in source
    assert "if not claimed:" in source
    assert "هذا الطلب محجوز حالياً" in source
    assert "تم حجز خطوة التنفيذ لهذا الطلب لمسؤول واحد فقط" in source


def test_transfer_cancel_keeps_the_claim_for_external_transfer_safety():
    source = _read("handlers/admin_transfer_policy.py")
    assert "keep the persistent claim" in source
    assert "release_order_fulfillment" not in source
    assert "تم الإبقاء على حجز التنفيذ لحماية الطلب من تكرار التحويل الخارجي" in source


def test_completion_requires_the_claiming_admin():
    source = _read("services/order_completion_service.py")
    assert "order_fulfillment_claims" in source
    assert "int(claim[\"admin_id\"]) != int(admin_id)" in source
    assert "release_claim_after_completion(conn, order_id, admin_id)" in source
    assert "ensure_fulfillment_claim_table" not in source


def test_administrative_closure_cannot_race_with_external_fulfillment():
    source = _read("handlers/admin_order_closure_policy.py")
    assert "get_fulfillment_claim" in source
    assert "if claim:" in source
    assert "تم منع الإغلاق الإداري" in source


def test_administrative_closure_locks_order_before_claim_check():
    source = _read("handlers/admin_order_closure_policy.py")
    assert "async def _load_order(conn, order_id: int, *, for_update: bool = False)" in source
    assert 'lock_clause = " FOR UPDATE" if for_update else ""' in source
    assert "order = await _load_order(conn, order_id, for_update=True)" in source
    assert "ensure_fulfillment_claim_table" not in source


def test_administrative_closure_binds_confirmation_to_order_and_admin_session():
    source = _read("handlers/admin_order_closure_policy.py")
    assert "admin_close_admin_id=callback.from_user.id" in source
    assert "pending_admin_id = data.get(\"admin_close_admin_id\")" in source
    assert "pending_admin_id != callback.from_user.id or pending_order_id != order_id" in source


def test_payment_confirmed_active_orders_expose_guarded_closure_action():
    source = _read("handlers/admin_order_list_policy.py")
    assert "payment_confirmed_admin_keyboard" in source
    assert "if status == \"payment_confirmed\"" in source
    assert "return payment_confirmed_admin_keyboard(order_id)" in source


def test_no_txid_uniqueness_rule_was_added():
    source = _read("services/order_fulfillment_claim.py")
    assert "UNIQUE (txid" not in source
    assert "unique (txid" not in source.lower()
