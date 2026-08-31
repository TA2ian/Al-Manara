"""Authoritative UTC timestamps and optional presentation-time rendering."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
DEFAULT_DISPLAY_TIMEZONE = ZoneInfo("Asia/Damascus")


def utc_now_naive() -> datetime:
    """Return the authoritative UTC timestamp for TIMESTAMP database columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def as_utc(value: datetime | None) -> datetime | None:
    """Normalize a stored timestamp to an aware UTC datetime."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def format_order_datetime(
    value: datetime | None,
    *,
    timezone_name: str | None = None,
) -> str:
    """Render a stored UTC timestamp for presentation only.

    Business decisions, deadlines, ordering, and comparisons must use UTC
    values directly; this formatter is intentionally presentation-only.
    """
    utc_value = as_utc(value)
    if utc_value is None:
        return "غير محددة"
    timezone_value = ZoneInfo(timezone_name) if timezone_name else DEFAULT_DISPLAY_TIMEZONE
    return utc_value.astimezone(timezone_value).strftime("%Y-%m-%d %H:%M")
