import io

import pytest
from PIL import Image

import services.media_security as media_security
from services.media_security import (
    MAX_UPLOAD_BYTES,
    validate_image_payload,
    validate_pdf_payload,
)


def _image_bytes(format_name: str = "PNG", size: tuple[int, int] = (32, 32)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, "white").save(output, format=format_name)
    return output.getvalue()


def test_valid_png_is_accepted():
    payload = _image_bytes("PNG")
    descriptor = validate_image_payload(payload, mime_type="image/png", file_name="qr.png")
    assert descriptor.kind == "image"
    assert descriptor.mime_type == "image/png"


def test_mime_extension_mismatch_is_rejected():
    payload = _image_bytes("PNG")
    with pytest.raises(ValueError, match="does not match"):
        validate_image_payload(payload, mime_type="image/jpeg", file_name="qr.jpg")


def test_fake_pdf_is_rejected_before_pdf_parsing():
    with pytest.raises(ValueError, match="valid PDF"):
        validate_pdf_payload(b"not-a-pdf", mime_type="application/pdf", file_name="proof.pdf")


def test_oversized_upload_is_rejected():
    with pytest.raises(ValueError, match="12 MB"):
        validate_image_payload(b"x" * (MAX_UPLOAD_BYTES + 1), mime_type="image/png", file_name="large.png")


def test_unsupported_extension_is_rejected():
    payload = _image_bytes("PNG")
    with pytest.raises(ValueError, match="unsupported image type"):
        validate_image_payload(payload, mime_type="application/octet-stream", file_name="payload.exe")


def test_image_pixel_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(media_security, "MAX_IMAGE_PIXELS", 100)
    payload = _image_bytes("PNG", (32, 32))
    with pytest.raises(ValueError, match="pixel count"):
        validate_image_payload(payload, mime_type="image/png", file_name="large.png")
