from pathlib import Path

from keyboards.admin_messaging import message_template_keyboard, personal_message_preview_keyboard
from keyboards.maintenance import maintenance_confirm_keyboard, maintenance_mode_keyboard
from services.admin_message_service import TEMPLATES, render_template
from services.maintenance_service import MaintenanceMode, MaintenanceService

ROOT = Path(__file__).resolve().parents[1]


def _callbacks(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_message_templates_are_fixed_and_branded():
    text = render_template("update", "سيتم تحسين الخدمة الليلة.", "ar", recipient_name="Grey")
    assert "تحديث من المنارة" in text
    assert "مرحباً Grey" in text
    assert "— <b>المنارة</b>" in text
    assert "<script>" not in render_template("update", "<script>alert(1)</script>")


def test_all_message_templates_render_in_both_languages():
    for key in TEMPLATES:
        assert "Al-Manara" in render_template(key, "Service update", "en")
        assert "المنارة" in render_template(key, "تحديث الخدمة", "ar")


def test_message_template_keyboard_requires_template_choice():
    callbacks = _callbacks(message_template_keyboard("admin_broadcast"))
    assert "admin_broadcast_template_update" in callbacks
    assert "admin_broadcast_template_maintenance" in callbacks
    assert "admin_broadcast_send" not in callbacks


def test_personal_message_preview_requires_explicit_send():
    callbacks = _callbacks(personal_message_preview_keyboard())
    assert "admin_personal_message_send" in callbacks
    assert "admin_personal_message_cancel" in callbacks


def test_maintenance_modes_are_explicit():
    assert {mode.value for mode in MaintenanceMode} == {"off", "limited", "maintenance", "emergency"}
    assert MaintenanceService.SETTING_KEY == "maintenance_mode"


def test_maintenance_mode_keyboard_never_executes_a_change_directly():
    callbacks = _callbacks(maintenance_mode_keyboard("off"))
    assert "admin_maintenance_mode_maintenance" in callbacks
    assert "admin_maintenance_mode_emergency" in callbacks
    assert "admin_maintenance_confirm_maintenance" not in callbacks


def test_maintenance_confirmation_targets_selected_mode():
    callbacks = _callbacks(maintenance_confirm_keyboard("maintenance"))
    assert callbacks == ["admin_maintenance_confirm_maintenance", "admin_menu"]


def test_maintenance_notice_is_localized():
    ar = MaintenanceService.user_notice(MaintenanceMode.MAINTENANCE, "ar")
    en = MaintenanceService.user_notice(MaintenanceMode.MAINTENANCE, "en")
    assert "وضع الصيانة" in ar
    assert "under maintenance" in en


def test_maintenance_state_is_database_authoritative_and_transition_is_atomic():
    source = (ROOT / "services" / "maintenance_service.py").read_text(encoding="utf-8")
    assert "SELECT value FROM bot_settings WHERE key = $1" in source
    assert "pg_advisory_xact_lock" in source
    assert "FOR UPDATE" in source
    assert "maintenance_mode_changed" in source
    assert "audit_logs" in source


def test_maintenance_admin_handler_delegates_transition_and_does_not_write_audit_directly():
    source = (ROOT / "handlers" / "admin_maintenance_policy.py").read_text(encoding="utf-8")
    assert "MaintenanceService.set_mode(target, admin_id=callback.from_user.id)" in source
    assert "INSERT INTO audit_logs" not in source
    assert "admin_maintenance_confirm_" in source
