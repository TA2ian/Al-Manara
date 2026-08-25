"""Centralized security boundary for user-supplied media.

This module deliberately performs cheap checks before any expensive parser,
OCR engine, QR decoder, or PDF renderer is invoked. Telegram metadata is
considered advisory; the payload itself is validated as the final boundary.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import fitz
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_WIDTH = 8000
MAX_IMAGE_HEIGHT = 8000
MAX_IMAGE_PIXELS = 40_000_000
MAX_PDF_PAGES = 1
MAX_PDF_PAGE_WIDTH = 5000.0
MAX_PDF_PAGE_HEIGHT = 5000.0

ALLOWED_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})
ALLOWED_IMAGE_SUFFIXES = frozenset({"jpg", "jpeg", "png", "webp"})
ALLOWED_DOCUMENT_MIMES = frozenset({"application/pdf"})
ALLOWED_DOCUMENT_SUFFIXES = frozenset({"pdf"})


@dataclass(frozen=True)
class MediaDescriptor:
    """Validated media metadata used by downstream handlers."""

    kind: str
    mime_type: str
    size: int
    file_name: str


def _normalized_mime(mime_type: str | None) -> str:
    return (mime_type or "").split(";", 1)[0].strip().lower()


def _suffix(file_name: str | None) -> str:
    name = file_name or ""
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def validate_upload_size(payload: bytes) -> None:
    if not payload:
        raise ValueError("uploaded file is empty")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("uploaded file exceeds the 2 MB limit")


def validate_image_payload(payload: bytes, *, mime_type: str | None = None, file_name: str | None = None) -> MediaDescriptor:
    """Validate actual image structure and resource limits before decoding further."""
    validate_upload_size(payload)
    mime = _normalized_mime(mime_type)
    suffix = _suffix(file_name)
    if mime and mime not in ALLOWED_IMAGE_MIMES and suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ValueError("unsupported image type")
    if suffix and suffix not in ALLOWED_IMAGE_SUFFIXES and mime not in ALLOWED_IMAGE_MIMES:
        raise ValueError("unsupported image type")

    try:
        with Image.open(io.BytesIO(payload)) as image:
            width, height = image.size
            if width < 1 or height < 1:
                raise ValueError("image has invalid dimensions")
            if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
                raise ValueError("image dimensions exceed the safety limit")
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError("image pixel count exceeds the safety limit")
            image.verify()
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("uploaded file is not a valid supported image") from exc

    detected_mime = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }
    try:
        with Image.open(io.BytesIO(payload)) as image:
            actual_mime = detected_mime.get(image.format or "")
    except Exception as exc:
        raise ValueError("unable to determine image format") from exc

    if actual_mime is None:
        raise ValueError("uploaded file is not a supported image format")
    if mime and mime in ALLOWED_IMAGE_MIMES and mime != actual_mime:
        raise ValueError("image content does not match its declared type")
    if suffix and suffix in ALLOWED_IMAGE_SUFFIXES:
        expected_suffix_mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }[suffix]
        if expected_suffix_mime != actual_mime:
            raise ValueError("image content does not match its file extension")

    return MediaDescriptor("image", actual_mime, len(payload), file_name or "upload")


def validate_pdf_payload(payload: bytes, *, mime_type: str | None = None, file_name: str | None = None) -> MediaDescriptor:
    """Validate a single-page PDF before rendering or text extraction."""
    validate_upload_size(payload)
    mime = _normalized_mime(mime_type)
    suffix = _suffix(file_name)
    if mime and mime not in ALLOWED_DOCUMENT_MIMES and suffix not in ALLOWED_DOCUMENT_SUFFIXES:
        raise ValueError("unsupported PDF type")
    if suffix and suffix not in ALLOWED_DOCUMENT_SUFFIXES and mime not in ALLOWED_DOCUMENT_MIMES:
        raise ValueError("unsupported PDF type")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("uploaded file is not a valid PDF")
    if mime and mime not in ALLOWED_DOCUMENT_MIMES:
        raise ValueError("PDF content does not match its declared type")
    if suffix and suffix not in ALLOWED_DOCUMENT_SUFFIXES:
        raise ValueError("PDF content does not match its file extension")

    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception as exc:
        raise ValueError("uploaded PDF is invalid or unreadable") from exc

    try:
        if document.page_count != MAX_PDF_PAGES:
            raise ValueError("PDF must contain exactly one page")
        page = document.load_page(0)
        rect = page.rect
        if rect.width <= 0 or rect.height <= 0:
            raise ValueError("PDF contains an invalid page")
        if rect.width > MAX_PDF_PAGE_WIDTH or rect.height > MAX_PDF_PAGE_HEIGHT:
            raise ValueError("PDF page dimensions exceed the safety limit")
    finally:
        document.close()

    return MediaDescriptor("pdf", "application/pdf", len(payload), file_name or "upload.pdf")


def validate_receipt_payload(payload: bytes, *, mime_type: str | None, file_name: str | None) -> MediaDescriptor:
    """Validate a receipt as either a supported image or a bounded PDF."""
    mime = _normalized_mime(mime_type)
    suffix = _suffix(file_name)
    if mime == "application/pdf" or suffix == "pdf":
        return validate_pdf_payload(payload, mime_type=mime_type, file_name=file_name)
    return validate_image_payload(payload, mime_type=mime_type, file_name=file_name)
