import io

import pytest
from PIL import Image

from services.receipt_media import (
    MAX_RECEIPT_BYTES,
    detect_receipt_media_type,
    normalize_receipt_media,
)


def _image_bytes(format_name: str = "PNG", size: tuple[int, int] = (64, 48)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, "white").save(output, format=format_name)
    return output.getvalue()


def test_pdf_is_classified_from_metadata_without_content_parsing():
    assert detect_receipt_media_type("application/pdf", "proof.pdf") == "pdf"
    assert detect_receipt_media_type(None, "proof.pdf") == "pdf"


def test_pdf_is_rejected_without_validating_or_parsing_payload():
    with pytest.raises(ValueError, match="PDF receipt detected"):
        normalize_receipt_media(
            b"not-a-pdf-and-never-parsed",
            "application/pdf",
            "proof.pdf",
        )


def test_image_is_normalized_for_ocr():
    payload = _image_bytes("PNG")
    normalized, mime_type = normalize_receipt_media(payload, "image/png", "proof.png")
    assert normalized
    assert mime_type == "image/jpeg"
    with Image.open(io.BytesIO(normalized)) as image:
        assert image.format == "JPEG"
        assert image.size == (64, 48)


def test_unsupported_media_is_rejected():
    with pytest.raises(ValueError, match="unsupported receipt format"):
        normalize_receipt_media(b"plain text", "text/plain", "proof.txt")


def test_receipt_size_limit_matches_central_media_limit():
    assert MAX_RECEIPT_BYTES == 2 * 1024 * 1024
