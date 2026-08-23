import io
from pathlib import Path

from PIL import Image

from services.media_security import validate_image_payload

ROOT = Path(__file__).resolve().parents[1]


def test_telegram_photo_payload_can_be_validated_without_advisory_metadata():
    output = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(output, format="JPEG")
    descriptor = validate_image_payload(output.getvalue(), file_name="telegram-photo")
    assert descriptor.kind == "image"
    assert descriptor.mime_type == "image/jpeg"


def test_sensitive_state_processing_lock_is_runtime_registered():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    middleware = (ROOT / "middleware" / "state_processing_lock.py").read_text(encoding="utf-8")
    assert "StateProcessingLockMiddleware" in bot
    assert "dp.message.middleware(StateProcessingLockMiddleware())" in bot
    assert "VerificationStates:waiting_shamcash_identity" in middleware
    assert "WalletStates:waiting_address" in middleware
    assert "WalletStates:waiting_qr" in middleware
    assert "ReceiptStates:waiting_receipt" in middleware
    assert "FeedbackStates:waiting_message" in middleware
    assert "pg_try_advisory_lock" in middleware


def test_support_has_strict_input_handlers():
    source = (ROOT / "handlers" / "feedback.py").read_text(encoding="utf-8")
    assert "FeedbackStates.waiting_message, F.text" in source
    assert "FeedbackStates.waiting_message, F.photo" in source
    assert "FeedbackStates.waiting_message, F.document" in source
    assert "application/pdf" in source
    assert "MAX_TEXT_LENGTH = 200" in source
