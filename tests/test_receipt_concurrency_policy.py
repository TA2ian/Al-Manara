from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_receipt_processing_uses_database_backed_order_lock():
    source = (ROOT / "services/receipt_processing_lock.py").read_text(encoding="utf-8")
    assert "pg_try_advisory_lock" in source
    assert "pg_advisory_unlock" in source
    assert "al-manara:receipt:" in source


def test_canonical_receipt_service_serializes_all_media_processing():
    source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    assert "from services.receipt_processing_lock import receipt_processing_lock" in source
    assert "async with receipt_processing_lock(int(order_id)) as acquired" in source
    assert "جارٍ التحقق من إيصال آخر لهذا الطلب" in source
    assert "if message.photo:" in source
    assert "elif message.document:" in source


def test_document_receipt_handler_delegates_to_canonical_service():
    source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    assert "from services.receipt_service import MAX_RECEIPT_ATTEMPTS, handle_receipt_upload" in source
    assert "await handle_receipt_upload(message, state)" in source
    assert "@serialize_receipt_handler" not in source


def test_multiple_receipts_do_not_create_parallel_attempts_for_one_order():
    source = (ROOT / "services/receipt_processing_lock.py").read_text(encoding="utf-8")
    assert "pg_try_advisory_lock(hashtextextended($1, 0))" in source
    assert "pg_advisory_unlock(hashtextextended($1, 0))" in source
