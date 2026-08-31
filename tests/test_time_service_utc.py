from datetime import datetime, timezone

from services.time_service import UTC, as_utc, format_order_datetime, utc_now_naive


def test_utc_now_naive_is_utc_and_naive_for_database_columns():
    value = utc_now_naive()
    assert value.tzinfo is None


def test_as_utc_attaches_utc_to_stored_naive_timestamp():
    value = as_utc(datetime(2026, 8, 31, 12, 0))
    assert value is not None
    assert value.tzinfo == timezone.utc
    assert value.hour == 12


def test_format_order_datetime_is_presentation_only():
    value = datetime(2026, 8, 31, 12, 0)
    rendered = format_order_datetime(value, timezone_name="UTC")
    assert rendered == "2026-08-31 12:00"
    assert UTC == timezone.utc
