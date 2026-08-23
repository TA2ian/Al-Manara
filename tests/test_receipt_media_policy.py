from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_receipt_document_policy_accepts_pdf_and_image_formats():
    source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    assert "application/pdf" in source
    assert "JPG/PNG/WebP" in source
    assert "normalize_receipt_media" in source
    assert "verify_shamcash_receipt" in source


def test_receipt_media_enforces_size_and_pdf_page_limits():
    source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    assert "MAX_RECEIPT_BYTES = 12 * 1024 * 1024" in source
    assert "MAX_PDF_PAGES = 3" in source
    assert "application/pdf" in source
    assert "document.page_count > MAX_PDF_PAGES" in source


def test_unsupported_receipt_files_are_explicitly_rejected():
    source = (ROOT / "handlers/receipt_document_policy.py").read_text(encoding="utf-8")
    assert "Unsupported proof format" in source
    assert "صيغة الإثبات غير مدعومة" in source


def test_photo_receipts_are_normalized_before_ocr():
    source = (ROOT / "services/receipt_service.py").read_text(encoding="utf-8")
    assert "normalize_receipt_media" in source
    assert "image_bytes, _ = normalize_receipt_media" in source
