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


def test_receipt_media_enforces_size_and_pdf_page_limits():
    source = (ROOT / "services/receipt_media.py").read_text(encoding="utf-8")
    security_source = (ROOT / "services/media_security.py").read_text(encoding="utf-8")
    assert "MAX_RECEIPT_BYTES = 12 * 1024 * 1024" in source
    assert "MAX_PDF_PAGES" in source
    assert "MAX_PDF_PAGES = 3" in security_source
    assert "OCR_MAX_DIMENSION = 1400" in source
    assert "application/pdf" in source
    assert "validate_pdf_payload" in source
    assert "document.page_count < 1 or document.page_count > MAX_PDF_PAGES" in security_source


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


import io

import fitz
import pytest
from PIL import Image

from services.media_security import (
    validate_image_payload,
    validate_pdf_payload,
)


def _make_image_bytes(image_format: str) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(output, format=image_format)
    return output.getvalue()


def _make_pdf_bytes(page_count: int) -> bytes:
    document = fitz.open()
    try:
        for _ in range(page_count):
            page = document.new_page(width=595, height=842)
            page.insert_text((72, 100), "ShamCash receipt")
        return document.tobytes()
    finally:
        document.close()


@pytest.mark.parametrize(
    ("image_format", "file_name", "mime_type"),
    [
        ("JPEG", "receipt.jpg", "image/jpeg"),
        ("PNG", "receipt.png", "image/png"),
        ("WEBP", "receipt.webp", "image/webp"),
    ],
)
def test_supported_images_are_validated_by_actual_content(image_format, file_name, mime_type):
    payload = _make_image_bytes(image_format)
    descriptor = validate_image_payload(
        payload,
        mime_type=mime_type,
        file_name=file_name,
    )
    assert descriptor.kind == "image"
    assert descriptor.mime_type == mime_type


def test_image_content_must_match_declared_mime_and_extension():
    payload = _make_image_bytes("PNG")

    with pytest.raises(ValueError, match="does not match"):
        validate_image_payload(
            payload,
            mime_type="image/jpeg",
            file_name="receipt.jpg",
        )


def test_pdf_page_limit_is_enforced_before_downstream_processing():
    payload = _make_pdf_bytes(4)

    with pytest.raises(ValueError, match="between 1 and 3 pages"):
        validate_pdf_payload(
            payload,
            mime_type="application/pdf",
            file_name="receipt.pdf",
        )


def test_three_page_pdf_is_accepted_by_the_security_boundary():
    payload = _make_pdf_bytes(3)

    descriptor = validate_pdf_payload(
        payload,
        mime_type="application/pdf",
        file_name="receipt.pdf",
    )

    assert descriptor.kind == "pdf"
    assert descriptor.mime_type == "application/pdf"
