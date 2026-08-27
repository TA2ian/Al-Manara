from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_maintenance_router_is_registered_in_authoritative_dispatcher():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "admin_maintenance_policy" in source
    assert "dp.include_router(admin_maintenance_policy.router)" in source
    assert not (ROOT / "handlers/admin.py").exists()


def test_admin_entry_precedes_customer_fsm_surfaces():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    admin_entry = source.index("dp.include_router(admin_entry.router)")
    admin_maintenance = source.index("dp.include_router(admin_maintenance_policy.router)")
    customer_settings = source.index("dp.include_router(customer_settings_policy.router)")
    order_amount = source.index("dp.include_router(order_amount_policy.router)")
    wallets = source.index("dp.include_router(wallets.router)")
    assert admin_entry < customer_settings
    assert admin_entry < order_amount
    assert admin_entry < wallets
    assert admin_maintenance < customer_settings
    assert admin_maintenance < order_amount
    assert admin_maintenance < wallets


def test_maintenance_checks_canonical_admin_access_before_customer_policy():
    source = (ROOT / "middleware/maintenance.py").read_text(encoding="utf-8")
    admin_check = "if AdminAccessService.is_admin(user_id):\n            return await handler(event, data)"
    assert "from services.admin_access_service import AdminAccessService" in source
    assert admin_check in source
    assert source.index("AdminAccessService.is_admin") < source.index("MaintenanceService.get_mode()")


def test_broadcast_requires_explicit_send_callback_and_does_not_send_from_input_capture():
    source = (ROOT / "handlers/admin_broadcast_policy.py").read_text(encoding="utf-8")
    capture_start = source.index("async def capture_broadcast")
    capture_end = source.index("@router.callback_query(F.data == \"admin_broadcast_edit\")")
    capture_source = source[capture_start:capture_end]
    assert "bot.send_message" not in capture_source
    assert "admin_broadcast_send" in source
    assert "@router.callback_query(F.data == \"admin_broadcast_send\")" in source


def test_personal_admin_message_targets_one_explicit_telegram_id():
    source = (ROOT / "handlers/admin_broadcast_policy.py").read_text(encoding="utf-8")
    personal_start = source.index("async def send_personal_message")
    personal_source = source[personal_start:]
    assert "await callback.message.bot.send_message(telegram_id, text" in personal_source
    assert "SELECT telegram_id, full_name, language, is_blocked FROM users WHERE telegram_id = $1" in personal_source


def test_retired_admin_compatibility_facade_is_removed():
    assert not (ROOT / "handlers/admin.py").exists()
    assert not (ROOT / "handlers/admin_settings_alias_policy.py").exists()
