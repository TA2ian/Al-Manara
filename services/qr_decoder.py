"""Robust QR decoding shared by customer verification flows."""
from __future__ import annotations

import io

from PIL import Image, ImageOps
from pyzbar.pyzbar import decode as pyzbar_decode


def decode_qr_bytes(raw_bytes: bytes) -> str:
    """Decode the first QR payload using multiple decoders/variants."""
    image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    variants = [image, ImageOps.autocontrast(image.convert("L")).convert("RGB")]

    # zxing-cpp is included in production requirements and handles many QR
    # images that pyzbar misses. Keep pyzbar as the first/compatible decoder.
    for variant in variants:
        try:
            decoded = pyzbar_decode(variant)
            if decoded:
                return decoded[0].data.decode("utf-8", errors="replace").strip()
        except Exception:
            pass
        try:
            import zxingcpp
            decoded = zxingcpp.read_barcodes(variant)
            if decoded:
                text = decoded[0].text
                if text:
                    return text.strip()
        except Exception:
            pass

    return ""
