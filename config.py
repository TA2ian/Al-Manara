"""Configuration module for Crypto Top-Up Bot."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/crypto_bot")

    # Webhook
    # On Replit, fall back to the public dev domain if WEBHOOK_HOST is not set
    _replit_domain = os.getenv("REPLIT_DEV_DOMAIN", "")
    WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", f"https://{_replit_domain}" if _replit_domain else "")
    WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 10000))

    # Security
    SECRET_TOKEN = os.getenv("SECRET_TOKEN", "")
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    # Rate Limiting
    RATE_LIMIT_COOLDOWN = int(os.getenv("RATE_LIMIT_COOLDOWN", 0))
    RATE_LIMIT_HOURLY = int(os.getenv("RATE_LIMIT_HOURLY", 1000))
    RATE_LIMIT_DAILY = int(os.getenv("RATE_LIMIT_DAILY", 10000))

    # Order Limits
    MIN_ORDER = float(os.getenv("MIN_ORDER", 10))
    MAX_ORDER = float(os.getenv("MAX_ORDER", 5000))
    DAILY_LIMIT = float(os.getenv("DAILY_LIMIT", 10000))

    # Payment
    PAYMENT_TIMEOUT = int(os.getenv("PAYMENT_TIMEOUT", 60))

    # Sham Cash
    SHAMCASH_USD_ACCOUNT = os.getenv("SHAMCASH_USD_ACCOUNT", "")
    SHAMCASH_SYP_ACCOUNT = os.getenv("SHAMCASH_SYP_ACCOUNT", "")
    SHAMCASH_NAME = os.getenv("SHAMCASH_NAME", "")

    # Fees
    SERVICE_FEE_PERCENT = float(os.getenv("SERVICE_FEE_PERCENT", 0))
    SERVICE_FEE_FIXED = float(os.getenv("SERVICE_FEE_FIXED", 0))

    # Backup
    BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", 30))

    # Maintenance — persisted in DB so it survives restarts.
    # Getter still synchronous for middleware; falls back to env var on first call,
    # then uses the DB-backed cache once the settings service is initialized.
    _maintenance_override: bool | None = None

    @classmethod
    def get_maintenance_mode(cls) -> bool:
        if cls._maintenance_override is not None:
            return cls._maintenance_override
        return os.getenv("MAINTENANCE_MODE", "false").lower() == "true"

    @classmethod
    def set_maintenance_mode_sync(cls, value: bool):
        """Set in-memory cache. Call persist_maintenance_mode() to save to DB."""
        cls._maintenance_override = value

    # ShamCash settings — can be overridden at runtime from DB
    _shamcash_name_override: str | None = None
    _shamcash_usd_override: str | None = None
    _shamcash_syp_override: str | None = None

    @classmethod
    def get_shamcash_name(cls) -> str:
        if cls._shamcash_name_override is not None:
            return cls._shamcash_name_override
        return cls.SHAMCASH_NAME

    @classmethod
    def get_shamcash_usd(cls) -> str:
        if cls._shamcash_usd_override is not None:
            return cls._shamcash_usd_override
        return cls.SHAMCASH_USD_ACCOUNT

    @classmethod
    def get_shamcash_syp(cls) -> str:
        if cls._shamcash_syp_override is not None:
            return cls._shamcash_syp_override
        return cls.SHAMCASH_SYP_ACCOUNT

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
    def validate(cls) -> list:
        """Validate required configuration."""
        errors = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")
        if not cls.ADMIN_IDS:
            errors.append("ADMIN_IDS is required")
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        return errors
