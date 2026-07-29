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
    RATE_LIMIT_COOLDOWN = int(os.getenv("RATE_LIMIT_COOLDOWN", 2))
    RATE_LIMIT_HOURLY = int(os.getenv("RATE_LIMIT_HOURLY", 100))
    RATE_LIMIT_DAILY = int(os.getenv("RATE_LIMIT_DAILY", 500))

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

    # Maintenance
    MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"

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
