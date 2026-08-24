"""Receipt media validation and normalization for OCR."""
from __future__ import annotations

import io

import fitz
from PIL import Image, ImageOps

from services.media_security import validate_image_payload, validate_pdf_payload

OCR_MAX_DIMENSION = 1400
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_DOCUMENT_MIMES = ALLOWED_IMAGE_MIMES | {"application/pdf"}
MAX_RECEIPT_BYTES = 2 * 1024 * 1024
MAX_RECEIPT_PDF_PAGES = 1


def normalize_receipt_media(payload: bytes, mime_type: str | None, file_name: str | None) -> tuple[bytes, str]:
    """Validate uploaded receipt media and return normalized PNG OCR input."""
    if not payload:
        raise ValueError("receipt file is empty")
    if len(payload) > MAX_RECEIPT_BYTES:
        raise ValueError("receipt file exceeds the 2 MB limit")

    mime = (mime_type or "").split(";", 1)[0].strip().lower()
    suffix = (file_name or "").lower().rsplit(".", 1)[-1] if "." in (file_name or "") else ""

    if mime == "application/pdf" or suffix == "pdf":
        validate_pdf_payload(payload, mime_type=mime_type, file_name=file_name)
        return _pdf_to_png(payload)

    validate_image_payload(payload, mime_type=mime_type, file_name=file_name)
    try:
        image = Image.open(io.BytesIO(payload)).convert("RGB")
    except Exception as exc:
        raise ValueError("uploaded file is not a valid image") from exc

    return _normalize_image(image), "image/png"


def _pdf_to_png(payload: bytes) -> tuple[bytes, str]:
    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception as exc:
        raise ValueError("uploaded PDF is invalid or unreadable") from exc

    try:
        if document.page_count != MAX_RECEIPT_PDF_PAGES:
            raise ValueError("receipt PDF must contain exactly one page")
        page = document.load_page(0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        return _normalize_image(image), "image/png"
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("failed to safely render PDF") from exc
    finally:
        document.close()


def _normalize_image(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image)
    image.thumbnail((OCR_MAX_DIMENSION, OCR_MAX_DIMENSION), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
