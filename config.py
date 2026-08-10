"""Application configuration for Al-Manara.

Environment variables contain deployment secrets and infrastructure settings.
Business settings that must survive restarts belong in the database/settings
service rather than being duplicated here.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [
        int(value.strip())
        for value in os.getenv("ADMIN_IDS", "").split(",")
        if value.strip()
    ]

    # Database: fail closed instead of silently using fake localhost credentials.
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Webhook
    WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "").rstrip("/")
    WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))

    # Security
    SECRET_TOKEN = os.getenv("SECRET_TOKEN", "")
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    # Rate limiting
    RATE_LIMIT_COOLDOWN = int(os.getenv("RATE_LIMIT_COOLDOWN", "5"))
    RATE_LIMIT_HOURLY = int(os.getenv("RATE_LIMIT_HOURLY", "100"))
    RATE_LIMIT_DAILY = int(os.getenv("RATE_LIMIT_DAILY", "500"))

    # Order limits
    MIN_ORDER = float(os.getenv("MIN_ORDER", "10"))
    MAX_ORDER = float(os.getenv("MAX_ORDER", "5000"))
    DAILY_LIMIT = float(os.getenv("DAILY_LIMIT", "10000"))

    # Payment
    PAYMENT_TIMEOUT = int(os.getenv("PAYMENT_TIMEOUT", "60"))

    # Legacy/default ShamCash values. Runtime administration should use the
    # database-backed SettingsService; these remain deployment fallbacks.
    SHAMCASH_USD_ACCOUNT = os.getenv("SHAMCASH_USD_ACCOUNT", "")
    SHAMCASH_SYP_ACCOUNT = os.getenv("SHAMCASH_SYP_ACCOUNT", "")
    SHAMCASH_NAME = os.getenv("SHAMCASH_NAME", "")

    # Legacy/default fees. Runtime administration should use SettingsService.
    SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", "0"))
    SERVICE_FEE_FIXED = float(os.getenv("SERVICE_FEE_FIXED", "0"))

    # Backup
    BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

    # Maintenance — persisted in DB and cached here for synchronous middleware.
    _maintenance_override: bool | None = None

    @classmethod
    def get_maintenance_mode(cls) -> bool:
        if cls._maintenance_override is not None:
            return cls._maintenance_override
        return os.getenv("MAINTENANCE_MODE", "false").lower() == "true"

    @classmethod
    def set_maintenance_mode_sync(cls, value: bool):
        """Update the in-memory cache; persistence is handled by SettingsService."""
        cls._maintenance_override = value

    # Runtime ShamCash overrides populated by SettingsService.
    _shamcash_name_override: str | None = None
    _shamcash_usd_override: str | None = None
    _shamcash_syp_override: str | None = None

    @classmethod
    def get_shamcash_name(cls) -> str:
        return cls._shamcash_name_override if cls._shamcash_name_override is not None else cls.SHAMCASH_NAME

    @classmethod
    def get_shamcash_usd(cls) -> str:
        return cls._shamcash_usd_override if cls._shamcash_usd_override is not None else cls.SHAMCASH_USD_ACCOUNT

    @classmethod
    def get_shamcash_syp(cls) -> str:
        return cls._shamcash_syp_override if cls._shamcash_syp_override is not None else cls.SHAMCASH_SYP_ACCOUNT

    @classmethod
    def set_shamcash_name(cls, value: str):
        cls._shamcash_name_override = value

    @classmethod
    def set_shamcash_usd(cls, value: str):
        cls._shamcash_usd_override = value

    @classmethod
    def set_shamcash_syp(cls, value: str):
        cls._shamcash_syp_override = value

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required production configuration and fail closed."""
        errors: list[str] = []

        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")
        if not cls.ADMIN_IDS:
            errors.append("ADMIN_IDS is required")
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        if not cls.WEBHOOK_HOST:
            errors.append("WEBHOOK_HOST is required for webhook mode")
        if not cls.SECRET_TOKEN:
            errors.append("SECRET_TOKEN is required for webhook mode")

        if cls.MIN_ORDER <= 0:
            errors.append("MIN_ORDER must be greater than 0")
        if cls.MAX_ORDER < cls.MIN_ORDER:
            errors.append("MAX_ORDER must be greater than or equal to MIN_ORDER")
        if cls.DAILY_LIMIT < cls.MAX_ORDER:
            errors.append("DAILY_LIMIT must be greater than or equal to MAX_ORDER")
        if not 0 <= cls.SERVICE_FEE_PERCENT <= 100:
            errors.append("SERVICE_FEE_PERCENT must be between 0 and 100")
        if cls.SERVICE_FEE_FIXED < 0:
            errors.append("SERVICE_FEE_FIXED cannot be negative")

        return errors
