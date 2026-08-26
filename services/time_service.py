"""Authoritative order timestamps and business-time rendering."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo("Asia/Damascus")


def utc_now_naive() -> datetime:
    """Return an authoritative UTC timestamp compatible with TIMESTAMP columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def format_order_datetime(value: datetime | None, *, timezone_name: str | None = None) -> str:
    """Render a stored UTC timestamp in the configured customer/business timezone."""
    if value is None:
        return "غير محددة"
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    tz = ZoneInfo(timezone_name) if timezone_name else BUSINESS_TIMEZONE
    return utc_value.astimezone(tz).strftime("%Y-%m-%d %H:%M")
