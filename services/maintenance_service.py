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
    """Own maintenance state while preserving the existing boolean setting."""

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
    def user_message_key(cls, mode: MaintenanceMode) -> str:
        return {
            MaintenanceMode.LIMITED: "maintenance_limited",
            MaintenanceMode.MAINTENANCE: "maintenance_mode",
            MaintenanceMode.EMERGENCY: "maintenance_emergency",
            MaintenanceMode.OFF: "maintenance_ended",
        }[mode]
