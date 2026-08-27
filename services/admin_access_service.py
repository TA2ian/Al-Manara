"""Canonical administrator identity and access policy."""
from __future__ import annotations

from config import Config


class AdminAccessService:
    """Single source of truth for administrator authorization."""

    @classmethod
    def is_admin(cls, user_id: int | None) -> bool:
        """Return whether the Telegram user is explicitly configured as an admin."""
        return Config.is_admin(user_id)

    @classmethod
    def require_admin(cls, user_id: int | None) -> None:
        """Raise when a caller attempts an administrator-only operation."""
        if not cls.is_admin(user_id):
            raise PermissionError("administrator access required")
