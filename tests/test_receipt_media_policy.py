from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_receipt_document_policy_rejects_pdf_and_routes_images_to_canonical_service():
    document_source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    service_source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    media_source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    verifier_source = (ROOT / "services/receipt_verifier.py").read_text(encoding="utf-8")
    assert "application/pdf" in media_source
    assert "PDF detected" in document_source
    assert "PDF contents are not processed automatically" in document_source
    assert "handle_receipt_upload" in document_source
    assert "normalize_receipt_media" in service_source
    assert "verify_shamcash_receipt" in service_source
    assert "verify_shamcash_receipt" in verifier_source


def test_receipt_media_uses_central_2mb_limit_and_does_not_parse_pdf():
    source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    security_source = (ROOT / "services/media_security.py").read_text(encoding="utf-8")
    assert "MAX_RECEIPT_BYTES = MAX_UPLOAD_BYTES" in source
    assert "OCR_MAX_DIMENSION = 1600" in source
    assert "application/pdf" in source
    assert "validate_pdf_payload" not in source
    assert "validate_pdf_payload" not in security_source


def test_unsupported_receipt_files_are_explicitly_rejected():
    source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    handler_source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    assert "unsupported receipt format; send JPG, PNG, or WebP" in source
    assert "JPG أو PNG أو WebP" in handler_source


def test_photo_receipts_are_normalized_before_ocr():
    source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    assert "normalize_receipt_media" in source
    assert "normalize_receipt_media(" in source
    assert "image_bytes" in source


def test_receipt_ocr_runs_off_the_asyncio_event_loop():
    source = (ROOT / "services/receipt_verifier.py").read_text(encoding="utf-8")
    assert "asyncio.to_thread(ReceiptVerifier._ocr_sync, image_bytes)" in source
    assert "OCR_TIMEOUT_SECONDS = 15" in source
    assert "receipt_ocr_completed elapsed_seconds" in source
