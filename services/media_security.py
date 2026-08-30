"""Centralized security boundary for user-supplied image media.

This module deliberately performs cheap checks before any expensive OCR
engine or QR decoder is invoked. Telegram metadata is considered advisory;
the payload itself is validated as the final boundary.

PDF files are intentionally outside this validation boundary. Receipt
handlers detect PDF submissions from Telegram metadata and reject them before
download, decoding, OCR, or any document parser is invoked.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_WIDTH = 8000
MAX_IMAGE_HEIGHT = 8000
MAX_IMAGE_PIXELS = 40_000_000

ALLOWED_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})
ALLOWED_IMAGE_SUFFIXES = frozenset({"jpg", "jpeg", "png", "webp"})


@dataclass(frozen=True)
class MediaDescriptor:
    """Validated image metadata used by downstream handlers."""

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


def validate_image_payload(
    payload: bytes,
    *,
    mime_type: str | None = None,
    file_name: str | None = None,
) -> MediaDescriptor:
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
