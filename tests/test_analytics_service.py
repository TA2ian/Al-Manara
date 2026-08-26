from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_analytics_service_is_the_single_query_owner():
    source = (ROOT / "services" / "analytics_service.py").read_text(encoding="utf-8")
    assert "class AnalyticsService" in source
    assert "async def dashboard" in source
    assert "async def financial" in source
    assert "FROM orders" in source
    assert "FROM users" in source


def test_admin_analytics_handler_delegates_to_service():
    source = (ROOT / "handlers" / "admin_navigation_policy.py").read_text(encoding="utf-8")
    assert "from services.analytics_service import AnalyticsService" in source
    assert "data = await AnalyticsService.dashboard()" in source
    assert "data = await AnalyticsService.financial()" in source
    assert "SELECT " not in source


def test_analytics_covers_core_operational_dimensions():
    source = (ROOT / "services" / "analytics_service.py").read_text(encoding="utf-8")
    for field in (
        "completed_orders",
        "rejected_orders",
        "expired_orders",
        "active_orders",
        "completed_usdt",
        "completed_fees",
        "average_completion_hours",
        "average_rating",
        "payment_currency",
        "network",
        "new_today",
        "new_30d",
    ):
        assert field in source


def test_startup_uses_canonical_maintenance_service():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from services.maintenance_service import MaintenanceMode, MaintenanceService" in source
    assert "maintenance_mode = await MaintenanceService.get_mode()" in source
    assert "SettingsService.get_bool('maintenance_mode'" not in source
