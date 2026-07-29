"""User model."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User entity."""
    id: int
    telegram_id: int
    username: Optional[str]
    full_name: Optional[str]
    shamcash_account: Optional[str]
    shamcash_qr_photo_id: Optional[str]
    language: str = "ar"
    terms_accepted: bool = False
    terms_accepted_at: Optional[datetime] = None
    is_verified: bool = False
    verification_status: str = "pending"
    is_blocked: bool = False
    created_at: Optional[datetime] = None


@dataclass
class UserVerification:
    """User verification data."""
    full_name: str
    shamcash_account: str
    shamcash_qr_photo_id: Optional[str] = None
