"""Canonical maintenance state, operational policy, and customer notifications."""
from __future__ import annotations

from enum import StrEnum

from aiogram import Bot

from database import get_pool
from services.settings_service import SettingsService


class MaintenanceMode(StrEnum):
    OFF = "off"
    LIMITED = "limited"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


class MaintenanceService:
    """Own database-backed maintenance state and durable customer notification jobs."""

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
                raw = await conn.fetchval("SELECT value FROM bot_settings WHERE key = $1", cls.SETTING_KEY)
            if raw is not None:
                return cls._parse_mode(str(raw))
        return cls._parse_mode(await SettingsService.get(cls.SETTING_KEY, "off"))

    @classmethod
    async def set_mode(cls, mode: MaintenanceMode, admin_id: int | None = None) -> MaintenanceMode:
        """Atomically change mode, audit it, and enqueue one notification per eligible customer."""
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

                users = await conn.fetch(
                    """SELECT u.telegram_id, EXISTS (
                           SELECT 1 FROM orders o WHERE o.user_id = u.id
                           AND o.status IN ('pending','waiting_payment','receipt_received','payment_confirmed')
                       ) AS has_active_order
                       FROM users u
                       WHERE u.terms_accepted = TRUE AND u.is_blocked = FALSE AND u.telegram_id IS NOT NULL"""
                )
                await conn.executemany(
                    """INSERT INTO maintenance_notification_jobs
                       (telegram_id, mode, has_active_order)
                       VALUES ($1, $2, $3)""",
                    [(int(user["telegram_id"]), target.value, bool(user["has_active_order"])) for user in users],
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
    async def notification_stats(cls, mode: MaintenanceMode) -> dict[str, int]:
        pool = await get_pool()
        if not pool:
            return {"queued": 0, "sent": 0, "failed": 0}
        async with pool.acquire() as conn:
            rows = await conn.fetchrow(
                """SELECT
                     COUNT(*) FILTER (WHERE status = 'pending') AS queued,
                     COUNT(*) FILTER (WHERE status = 'sent') AS sent,
                     COUNT(*) FILTER (WHERE status = 'failed') AS failed
                   FROM maintenance_notification_jobs WHERE mode = $1""",
                MaintenanceMode(mode).value,
            )
        return {key: int(rows[key] or 0) for key in ("queued", "sent", "failed")}

    @classmethod
    async def process_notification_jobs(cls, bot: Bot, batch_size: int = 50) -> int:
        """Claim and deliver a bounded notification batch; safe across multiple workers."""
        pool = await get_pool()
        if not pool:
            return 0
        async with pool.acquire() as conn:
            async with conn.transaction():
                jobs = await conn.fetch(
                    """WITH claimed AS (
                           SELECT id FROM maintenance_notification_jobs
                           WHERE status = 'pending' AND available_at <= NOW()
                           ORDER BY id FOR UPDATE SKIP LOCKED LIMIT $1
                       )
                       UPDATE maintenance_notification_jobs j
                       SET status = 'processing', locked_at = NOW(), attempts = attempts + 1
                       FROM claimed c WHERE j.id = c.id
                       RETURNING j.id, j.telegram_id, j.mode, j.has_active_order""",
                    batch_size,
                )
        processed = 0
        for job in jobs:
            try:
                user_lang = "ar"
                async with pool.acquire() as conn:
                    stored = await conn.fetchval("SELECT language FROM users WHERE telegram_id = $1", job["telegram_id"])
                if stored in ("ar", "en"):
                    user_lang = stored
                await bot.send_message(job["telegram_id"], cls.user_notice(MaintenanceMode(job["mode"]), user_lang, has_active_order=job["has_active_order"]), parse_mode="HTML")
            except Exception as exc:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE maintenance_notification_jobs
                           SET status = CASE WHEN attempts >= 5 THEN 'failed' ELSE 'pending' END,
                               available_at = NOW() + CASE WHEN attempts >= 5 THEN INTERVAL '0 seconds' ELSE INTERVAL '2 minutes' END,
                               last_error = $2 WHERE id = $1""",
                        job["id"], str(exc)[:1000],
                    )
            else:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE maintenance_notification_jobs SET status = 'sent', sent_at = NOW(), last_error = NULL WHERE id = $1", job["id"])
            processed += 1
        return processed
