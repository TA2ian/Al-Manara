"""Persistent settings service backed by the database."""
import logging

from database import get_pool

logger = logging.getLogger(__name__)


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
        """Persist a setting before publishing it to the process cache."""
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO bot_settings (key, value)
                       VALUES ($1, $2)
                       ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                    key,
                    value,
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
