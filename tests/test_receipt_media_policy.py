from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_receipt_document_policy_accepts_pdf_and_image_formats():
    document_source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    service_source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    media_source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    verifier_source = (ROOT / "services/receipt_verifier.py").read_text(encoding="utf-8")
    assert "application/pdf" in media_source
    assert "JPG/PNG/WebP" in document_source
    assert "handle_receipt_upload" in document_source
    assert "normalize_receipt_media" in service_source
    assert "verify_shamcash_receipt" in service_source
    assert "verify_shamcash_receipt" in verifier_source


def test_receipt_media_enforces_2mb_size_and_one_page_pdf_limit():
    source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    assert "MAX_RECEIPT_BYTES = 2 * 1024 * 1024" in source
    assert "MAX_RECEIPT_PDF_PAGES = 1" in source
    assert "document.page_count != MAX_RECEIPT_PDF_PAGES" in source
    assert "OCR_MAX_DIMENSION = 1400" in source
    assert "application/pdf" in source
    assert "validate_pdf_payload" in source


def test_unsupported_receipt_files_are_explicitly_rejected():
    source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    assert "Unsupported proof format" in source
    assert "صيغة الإثبات غير مدعومة" in source


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
