"""Persistent settings service backed by the database."""
import logging

from database import get_pool

logger = logging.getLogger(__name__)


_SHAMCASH_PAYMENT_METHODS = {
    "shamcash_usd": ("shamcash_usd", "USD"),
    "shamcash_syp": ("shamcash_new_syp", "NEW.SYP"),
}


class SettingsService:
    """Settings stored in DB and cached in memory for fast access."""

    _cache: dict[str, str] = {}
    _initialized: bool = False

    @classmethod
    async def init(cls):
        """Load all settings from DB into cache once."""
        if cls._initialized:
            return
        await cls.reload()

    @classmethod
    async def reload(cls):
        """Reload settings from DB and replace the in-memory cache."""
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT key, value FROM bot_settings")
                cls._cache = {row["key"]: row["value"] for row in rows}
        else:
            cls._cache = {}
        cls._initialized = True
        logger.info("Settings cache reloaded: %d keys", len(cls._cache))

    @classmethod
    async def get(cls, key: str, default: str = "") -> str:
        if not cls._initialized:
            await cls.init()
        return cls._cache.get(key, default)

    @classmethod
    async def set(cls, key: str, value: str):
        """Persist a setting and keep legacy ShamCash settings synchronized with payment methods."""
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """INSERT INTO bot_settings (key, value)
                           VALUES ($1, $2)
                           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                        key,
                        value,
                    )
                    payment_method = _SHAMCASH_PAYMENT_METHODS.get(key)
                    if payment_method:
                        method_code, currency = payment_method
                        await conn.execute(
                            """UPDATE payment_methods
                               SET account_identifier = $1,
                                   updated_at = NOW()
                             WHERE provider = 'ShamCash'
                               AND code = $2
                               AND currency = $3""",
                            value,
                            method_code,
                            currency,
                        )
        cls._cache[key] = value
        cls._initialized = True
        logger.info("Setting saved: %s", key)

    @classmethod
    async def get_bool(cls, key: str, default: bool = False) -> bool:
        val = await cls.get(key, "")
        if not val:
            return default
        return val.lower() in ("1", "true", "yes", "on")

    @classmethod
    async def set_bool(cls, key: str, value: bool):
        await cls.set(key, "1" if value else "0")
