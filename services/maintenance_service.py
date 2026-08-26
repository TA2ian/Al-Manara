"""Canonical maintenance state and operational policy."""
from __future__ import annotations

from enum import StrEnum

from database import get_pool
from services.settings_service import SettingsService


class MaintenanceMode(StrEnum):
    OFF = "off"
    LIMITED = "limited"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


class MaintenanceService:
    """Own the database-backed maintenance state and its transition policy."""

    SETTING_KEY = "maintenance_mode"
    VALID_MODES = {mode.value for mode in MaintenanceMode}
    LOCK_KEY = "al-manara:maintenance-mode"

    @classmethod
    def _parse_mode(cls, raw: str | None) -> MaintenanceMode:
        if raw in ("1", "true", "yes", "on"):
            return MaintenanceMode.MAINTENANCE
        if raw in cls.VALID_MODES:
            return MaintenanceMode(raw)
        return MaintenanceMode.OFF

    @classmethod
    async def get_mode(cls) -> MaintenanceMode:
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                raw = await conn.fetchval(
                    "SELECT value FROM bot_settings WHERE key = $1",
                    cls.SETTING_KEY,
                )
            if raw is not None:
                return cls._parse_mode(str(raw))
        return cls._parse_mode(await SettingsService.get(cls.SETTING_KEY, "off"))

    @classmethod
    async def set_mode(cls, mode: MaintenanceMode, admin_id: int | None = None) -> MaintenanceMode:
        """Atomically change the mode and write its audit record when an admin performs it."""
        target = MaintenanceMode(mode)
        pool = await get_pool()
        if not pool:
            await SettingsService.set(cls.SETTING_KEY, target.value)
            return target

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1))",
                    cls.LOCK_KEY,
                )
                current_raw = await conn.fetchval(
                    "SELECT value FROM bot_settings WHERE key = $1 FOR UPDATE",
                    cls.SETTING_KEY,
                )
                current = cls._parse_mode(str(current_raw) if current_raw is not None else None)
                if current == target:
                    return current

                await conn.execute(
                    """INSERT INTO bot_settings (key, value)
                       VALUES ($1, $2)
                       ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                    cls.SETTING_KEY,
                    target.value,
                )

                if admin_id is not None:
                    severity = (
                        "critical"
                        if target == MaintenanceMode.EMERGENCY
                        else "warning"
                        if target != MaintenanceMode.OFF
                        else "info"
                    )
                    await conn.execute(
                        """INSERT INTO audit_logs
                           (admin_id, action, details, new_value, severity)
                           VALUES ($1, $2, $3, $4, $5)""",
                        admin_id,
                        "maintenance_mode_changed",
                        f"Maintenance mode changed from {current.value} to {target.value}",
                        target.value,
                        severity,
                    )

        return target

    @classmethod
    async def is_blocking_new_orders(cls) -> bool:
        return (await cls.get_mode()) in {
            MaintenanceMode.MAINTENANCE,
            MaintenanceMode.EMERGENCY,
        }

    @classmethod
    async def allows_active_order_lifecycle(cls) -> bool:
        return (await cls.get_mode()) != MaintenanceMode.EMERGENCY

    @classmethod
    def user_notice(cls, mode: MaintenanceMode, lang: str = "ar") -> str:
        if lang == "en":
            return {
                MaintenanceMode.LIMITED: "🟡 <b>Limited service</b>\n\nSome operations may be temporarily restricted while we improve the service. Existing requests remain protected.",
                MaintenanceMode.MAINTENANCE: "🛠️ <b>Al-Manara is under maintenance</b>\n\nNew operations are temporarily unavailable. Existing requests remain protected and will continue according to their current status. Please try again when service is restored.",
                MaintenanceMode.EMERGENCY: "🚨 <b>Temporary service interruption</b>\n\nNew operations are currently unavailable while we address an urgent operational issue. Please do not send any payment outside an official order flow.",
                MaintenanceMode.OFF: "",
            }[mode]
        return {
            MaintenanceMode.LIMITED: "🟡 <b>الخدمة تعمل بوضع محدود</b>\n\nقد تكون بعض العمليات مقيدة مؤقتاً أثناء تحسين الخدمة. الطلبات الحالية تبقى محفوظة ومحمية.",
            MaintenanceMode.MAINTENANCE: "🛠️ <b>المنارة في وضع الصيانة</b>\n\nتم إيقاف إنشاء العمليات الجديدة مؤقتاً. طلباتك الحالية محفوظة ومحمية وتستمر وفق حالتها الحالية. حاول مجدداً بعد عودة الخدمة.",
            MaintenanceMode.EMERGENCY: "🚨 <b>توقف مؤقت للخدمة</b>\n\nتم إيقاف العمليات الجديدة مؤقتاً لمعالجة حالة تشغيلية عاجلة. لا ترسل أي دفعة خارج مسار طلب رسمي.",
            MaintenanceMode.OFF: "",
        }[mode]
