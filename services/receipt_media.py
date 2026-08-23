"""Receipt media validation and normalization for OCR."""
from __future__ import annotations

import io

import fitz
from PIL import Image, ImageOps

MAX_RECEIPT_BYTES = 12 * 1024 * 1024
MAX_PDF_PAGES = 3
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_DOCUMENT_MIMES = ALLOWED_IMAGE_MIMES | {"application/pdf"}


def normalize_receipt_media(payload: bytes, mime_type: str | None, file_name: str | None) -> tuple[bytes, str]:
    """Validate uploaded media and return a normalized PNG suitable for OCR."""
    if not payload or len(payload) > MAX_RECEIPT_BYTES:
        raise ValueError("receipt file is empty or exceeds the 12 MB limit")

    mime = (mime_type or "").split(";", 1)[0].strip().lower()
    suffix = (file_name or "").lower().rsplit(".", 1)[-1] if "." in (file_name or "") else ""
    if mime not in ALLOWED_DOCUMENT_MIMES and suffix not in {"jpg", "jpeg", "png", "webp", "pdf"}:
        raise ValueError("unsupported receipt file type")

    if mime == "application/pdf" or suffix == "pdf":
        return _pdf_to_png(payload)

    try:
        image = Image.open(io.BytesIO(payload))
        image.verify()
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
        if document.page_count < 1 or document.page_count > MAX_PDF_PAGES:
            raise ValueError("PDF must contain between 1 and 3 pages")
        page = document.load_page(0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        return _normalize_image(image), "image/png"
    finally:
        document.close()


def _normalize_image(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image)
    image.thumbnail((2200, 2200), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
