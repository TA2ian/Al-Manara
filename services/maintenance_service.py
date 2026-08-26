"""Canonical maintenance state, operational policy, and customer notifications."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from enum import StrEnum

from database import get_pool
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class MaintenanceMode(StrEnum):
    OFF = "off"
    LIMITED = "limited"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


class MaintenanceService:
    """Own database-backed maintenance state and customer notification policy."""

    SETTING_KEY = "maintenance_mode"
    VALID_MODES = {mode.value for mode in MaintenanceMode}
    LOCK_KEY = "al-manara:maintenance-mode"
    NOTIFICATION_DELAY_SECONDS = 0.05

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
                raw = await conn.fetchval("SELECT value FROM bot_settings WHERE key = $1", cls.SETTING_KEY)
            if raw is not None:
                return cls._parse_mode(str(raw))
        return cls._parse_mode(await SettingsService.get(cls.SETTING_KEY, "off"))

    @classmethod
    async def set_mode(cls, mode: MaintenanceMode, admin_id: int | None = None) -> MaintenanceMode:
        """Atomically change the mode and audit an administrative transition."""
        target = MaintenanceMode(mode)
        pool = await get_pool()
        if not pool:
            await SettingsService.set(cls.SETTING_KEY, target.value)
            return target

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", cls.LOCK_KEY)
                current_raw = await conn.fetchval("SELECT value FROM bot_settings WHERE key = $1 FOR UPDATE", cls.SETTING_KEY)
                current = cls._parse_mode(str(current_raw) if current_raw is not None else None)
                if current == target:
                    return current
                await conn.execute(
                    """INSERT INTO bot_settings (key, value) VALUES ($1, $2)
                       ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                    cls.SETTING_KEY, target.value,
                )
                if admin_id is not None:
                    severity = "critical" if target == MaintenanceMode.EMERGENCY else "warning" if target != MaintenanceMode.OFF else "info"
                    await conn.execute(
                        """INSERT INTO audit_logs (admin_id, action, details, new_value, severity)
                           VALUES ($1, $2, $3, $4, $5)""",
                        admin_id, "maintenance_mode_changed",
                        f"Maintenance mode changed from {current.value} to {target.value}",
                        target.value, severity,
                    )
        return target

    @classmethod
    async def is_blocking_new_orders(cls) -> bool:
        return (await cls.get_mode()) in {MaintenanceMode.MAINTENANCE, MaintenanceMode.EMERGENCY}

    @classmethod
    async def allows_active_order_lifecycle(cls) -> bool:
        return (await cls.get_mode()) != MaintenanceMode.EMERGENCY

    @classmethod
    def user_notice(cls, mode: MaintenanceMode, lang: str = "ar", *, has_active_order: bool = False) -> str:
        if lang == "en":
            if mode == MaintenanceMode.LIMITED:
                return "🟡 <b>Al-Manara is operating in limited mode</b>\n\nSome non-essential operations may be temporarily restricted while we improve the service." + ("\n\n<b>Your active order remains protected.</b>" if has_active_order else "")
            if mode == MaintenanceMode.MAINTENANCE:
                return "🛠️ <b>Al-Manara is under maintenance</b>\n\nNew operations are temporarily unavailable." + ("\n\n<b>Your active order remains protected and continues according to its current status.</b>" if has_active_order else "\n\nExisting requests remain protected and will continue according to their current status.") + "\n\nPlease try again when service is restored."
            if mode == MaintenanceMode.EMERGENCY:
                return "🚨 <b>Temporary service interruption</b>\n\nNew operations and customer interactions are temporarily restricted while we address an urgent operational issue." + ("\n\n<b>Your active order is retained safely for administrative handling.</b>" if has_active_order else "") + "\n\nDo not send any payment outside an official order flow."
            return ""

        if mode == MaintenanceMode.LIMITED:
            return "🟡 <b>المنارة تعمل بوضع محدود</b>\n\nقد تكون بعض العمليات غير الأساسية مقيدة مؤقتاً أثناء تحسين الخدمة." + ("\n\n<b>طلبك النشط محفوظ ومحمِي.</b>" if has_active_order else "")
        if mode == MaintenanceMode.MAINTENANCE:
            return "🛠️ <b>المنارة في وضع الصيانة</b>\n\nتم إيقاف إنشاء العمليات الجديدة مؤقتاً." + ("\n\n<b>طلبك النشط محفوظ ومحمِي ويستمر وفق حالته الحالية.</b>" if has_active_order else "\n\nطلباتك الحالية محفوظة ومحمية وتستمر وفق حالتها الحالية.") + "\n\nحاول مجدداً بعد عودة الخدمة."
        if mode == MaintenanceMode.EMERGENCY:
            return "🚨 <b>توقف مؤقت للخدمة</b>\n\nتم تقييد العمليات وتفاعل المستخدمين مؤقتاً لمعالجة حالة تشغيلية عاجلة." + ("\n\n<b>طلبك النشط محفوظ بأمان وتتم إدارته وفق إجراءات التشغيل.</b>" if has_active_order else "") + "\n\nلا ترسل أي دفعة خارج مسار طلب رسمي."
        return ""

    @classmethod
    async def notify_customers(cls, bot: Bot, mode: MaintenanceMode) -> dict[str, int]:
        """Notify eligible customers after a committed maintenance transition."""
        target = MaintenanceMode(mode)
        pool = await get_pool()
        if not pool:
            return {"sent": 0, "failed": 0, "total": 0}
        async with pool.acquire() as conn:
            users = await conn.fetch(
                """SELECT u.telegram_id, u.language, EXISTS (
                       SELECT 1 FROM orders o WHERE o.user_id = u.id
                       AND o.status IN ('pending','waiting_payment','receipt_received','payment_confirmed')
                   ) AS has_active_order
                   FROM users u
                   WHERE u.terms_accepted = TRUE AND u.is_blocked = FALSE AND u.telegram_id IS NOT NULL
                   ORDER BY u.id"""
            )
        sent = failed = 0
        for user in users:
            lang = user["language"] if user["language"] in ("ar", "en") else "ar"
            text = cls.user_notice(target, lang, has_active_order=bool(user["has_active_order"]))
            if not text:
                continue
            try:
                await bot.send_message(user["telegram_id"], text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
                logger.warning("Maintenance notification failed for telegram_id=%s", user["telegram_id"], exc_info=True)
            await asyncio.sleep(cls.NOTIFICATION_DELAY_SECONDS)
        return {"sent": sent, "failed": failed, "total": len(users)}
