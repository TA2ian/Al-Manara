from services.maintenance_service import MaintenanceMode, MaintenanceService


def test_maintenance_notice_marks_active_order_as_protected():
    notice = MaintenanceService.user_notice(MaintenanceMode.MAINTENANCE, "ar", has_active_order=True)
    assert "طلبك النشط محفوظ" in notice
    assert "إيقاف إنشاء العمليات الجديدة" in notice


def test_emergency_notice_warns_against_official_order_bypass():
    notice = MaintenanceService.user_notice(MaintenanceMode.EMERGENCY, "ar", has_active_order=False)
    assert "لا ترسل أي دفعة خارج مسار طلب رسمي" in notice


def test_limited_mode_is_informational_for_active_customer():
    notice = MaintenanceService.user_notice(MaintenanceMode.LIMITED, "ar", has_active_order=True)
    assert "بوضع محدود" in notice
    assert "طلبك النشط محفوظ ومحمِي" in notice


def test_off_mode_has_no_customer_notice():
    assert MaintenanceService.user_notice(MaintenanceMode.OFF, "ar") == ""
