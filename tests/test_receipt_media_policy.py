from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_receipt_document_policy_accepts_pdf_and_image_formats():
    document_source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    media_source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    assert "application/pdf" in media_source
    assert "JPG/PNG/WebP" in document_source
    assert "normalize_receipt_media" in document_source
    assert "verify_shamcash_receipt" in document_source


def test_receipt_media_enforces_size_and_pdf_page_limits():
    source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    assert "MAX_RECEIPT_BYTES = 12 * 1024 * 1024" in source
    assert "MAX_PDF_PAGES = 3" in source
    assert "OCR_MAX_DIMENSION = 1400" in source
    assert "application/pdf" in source
    assert "document.page_count < 1 or document.page_count > MAX_PDF_PAGES" in source


def test_unsupported_receipt_files_are_explicitly_rejected():
    source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    assert "Unsupported proof format" in source
    assert "صيغة الإثبات غير مدعومة" in source


def test_photo_receipts_are_normalized_before_ocr():
    source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    assert "normalize_receipt_media" in source
    assert "image_bytes, _ = normalize_receipt_media" in source


def test_receipt_ocr_runs_off_the_asyncio_event_loop():
    source = (ROOT / "services/receipt_verifier.py").read_text(encoding="utf-8")
    assert "asyncio.to_thread(ReceiptVerifier._ocr_sync, image_bytes)" in source
    assert "OCR_TIMEOUT_SECONDS = 15" in source
    assert "receipt_ocr_completed elapsed_seconds" in source
