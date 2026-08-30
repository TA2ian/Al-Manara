"""Receipt media validation and OCR preprocessing."""
from __future__ import annotations

import io

from PIL import Image, ImageOps

from services.media_security import validate_image_payload, validate_pdf_payload

OCR_MAX_DIMENSION = 1600
OCR_JPEG_QUALITY = 82
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_DOCUMENT_MIMES = ALLOWED_IMAGE_MIMES | {"application/pdf"}
MAX_RECEIPT_BYTES = 12 * 1024 * 1024


def detect_receipt_media_type(mime_type: str | None, file_name: str | None) -> str:
    """Classify a submission without decoding or rendering its contents."""
    mime = (mime_type or "").split(";", 1)[0].strip().lower()
    name = (file_name or "").lower()
    suffix = name.rsplit(".", 1)[-1] if "." in name else ""
    if mime == "application/pdf" or suffix == "pdf":
        return "pdf"
    if mime in ALLOWED_IMAGE_MIMES or suffix in {"jpg", "jpeg", "png", "webp"}:
        return "image"
    return "unsupported"


def normalize_receipt_media(payload: bytes, mime_type: str | None, file_name: str | None) -> tuple[bytes, str]:
    """Validate an image and create a compressed OCR-only copy.

    PDFs are validated only as documents and are deliberately never rendered,
    converted, or passed to OCR. The caller must instruct the customer to open
    the PDF and submit a screenshot instead.
    """
    if not payload:
        raise ValueError("receipt file is empty")
    if len(payload) > MAX_RECEIPT_BYTES:
        raise ValueError("receipt file exceeds the 12 MB limit")

    media_type = detect_receipt_media_type(mime_type, file_name)
    if media_type == "pdf":
        validate_pdf_payload(payload, mime_type=mime_type, file_name=file_name)
        raise ValueError(
            "PDF receipt detected. Open the PDF, display the payment receipt, take a screenshot, and send the screenshot instead."
        )
    if media_type != "image":
        raise ValueError("unsupported receipt format; send JPG, PNG, or WebP")

    validate_image_payload(payload, mime_type=mime_type, file_name=file_name)
    try:
        image = Image.open(io.BytesIO(payload))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise ValueError("uploaded file is not a valid image") from exc

    return _prepare_image_for_ocr(image), "image/jpeg"


def _prepare_image_for_ocr(image: Image.Image) -> bytes:
    """Resize and JPEG-compress an OCR working copy without replacing the original."""
    image.thumbnail((OCR_MAX_DIMENSION, OCR_MAX_DIMENSION), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=OCR_JPEG_QUALITY,
        optimize=True,
        progressive=True,
    )
    return output.getvalue()
