"""Encryption service for sensitive data."""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting sensitive data."""

    def __init__(self, key: str):
        self._key = self._derive_key(key)
        self._cipher = Fernet(self._key)

    def _derive_key(self, password: str) -> bytes:
        """Derive key from password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'crypto_bot_salt_v1',
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def encrypt(self, data: str) -> str:
        """Encrypt string."""
        if not data:
            return data
        return self._cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string."""
        if not encrypted_data:
            return encrypted_data
        try:
            return self._cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data
