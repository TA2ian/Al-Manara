"""Canonical maintenance state and operational policy."""
from __future__ import annotations

from enum import StrEnum

from services.settings_service import SettingsService


class MaintenanceMode(StrEnum):
    OFF = "off"
    LIMITED = "limited"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


class MaintenanceService:
    """Own maintenance state while preserving compatibility with the old setting."""

    SETTING_KEY = "maintenance_mode"
    VALID_MODES = {mode.value for mode in MaintenanceMode}

    @classmethod
    async def get_mode(cls) -> MaintenanceMode:
        raw = await SettingsService.get(cls.SETTING_KEY, "off")
        if raw in ("1", "true", "yes", "on"):
            return MaintenanceMode.MAINTENANCE
        return MaintenanceMode(raw) if raw in cls.VALID_MODES else MaintenanceMode.OFF

    @classmethod
    async def set_mode(cls, mode: MaintenanceMode):
        await SettingsService.set(cls.SETTING_KEY, mode.value)

    @classmethod
    async def is_blocking_new_orders(cls) -> bool:
        return (await cls.get_mode()) in {MaintenanceMode.MAINTENANCE, MaintenanceMode.EMERGENCY}

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
