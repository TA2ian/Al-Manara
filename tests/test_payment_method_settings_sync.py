"""Regression coverage for the canonical ShamCash admin setup wizard."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_payment_method_setup_is_a_single_sequential_wizard():
    source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert "waiting_recipient_name" in source
    assert "waiting_receiving_address" in source
    assert "waiting_qr" in source
    assert "admin_pm_setup_confirm" in source
    assert "اسم المستلم" in source
    assert "عنوان الاستلام" in source
    assert "رمز QR" in source


def test_payment_method_qr_must_match_receiving_address_before_save():
    source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert "qr_address.casefold() != address.casefold()" in source
    assert "qr_address" in source
    assert "receiving_address" in source
    assert "qr_address_verified=true" in source


def test_payment_method_setup_writes_all_three_authoritative_values_together():
    source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert "SET recipient_name=$1, account_identifier=$2, qr_photo_id=$3" in source
    assert "UPDATE payment_methods" in source
    assert "provider='ShamCash'" in source


def test_payment_method_setup_callbacks_cannot_capture_confirmation_callback():
    source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert 'F.data.startswith("admin_pm_setup_")' not in source
    assert 'F.data.regexp(rf"^admin_pm_setup_{CANONICAL_CODE_PATTERN}$")' in source
    assert 'F.data == "admin_pm_setup_confirm"' in source


def test_payment_method_enable_and_disable_callbacks_are_exactly_scoped():
    source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert "admin_pm_enable_" in source
    assert "admin_pm_disable_" in source
    assert 'F.data.regexp(rf"^admin_pm_enable_{CANONICAL_CODE_PATTERN}$")' in source
    assert 'F.data.regexp(rf"^admin_pm_disable_{CANONICAL_CODE_PATTERN}$")' in source
    assert 'F.data.regexp(rf"^admin_pm_toggle_{CANONICAL_CODE_PATTERN}$")' in source


def test_payment_method_enable_requires_complete_configuration():
    source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert 'if not method["recipient_name"]' in source
    assert 'if not method["account_identifier"]' in source
    assert 'if not method["qr_photo_id"]' in source
    assert "لا يمكن تفعيل وسيلة الدفع قبل إكمال إعدادها" in source


def test_payment_method_setup_preserves_existing_enabled_state():
    source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert "RETURNING currency, enabled" in source
    assert 'reply_markup=_view_keyboard(code, row["enabled"])' in source


def test_payment_method_toggle_renders_directly_without_reusing_view_callback():
    source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    marker = "async def _set_payment_method_enabled"
    start = source.index(marker)
    end = source.index("@router.callback_query", start)
    toggle_block = source[start:end]
    assert "await payment_method_view(callback)" not in toggle_block
    assert "await callback.message.edit_text" in toggle_block
    assert 'await callback.answer("تم التفعيل" if enabled else "تم التعطيل")' in toggle_block


def test_legacy_payment_method_callbacks_accept_known_historical_aliases_only():
    source = (ROOT / "handlers/payment_method_legacy_compat.py").read_text(encoding="utf-8")
    assert '"USD": "shamcash_usd"' in source
    assert '"usd": "shamcash_usd"' in source
    assert '"shamcash_usd": "shamcash_usd"' in source
    assert '"shamcash_USD": "shamcash_usd"' in source
    assert '"NEW.SYP": "shamcash_new_syp"' in source
    assert '"new.syp": "shamcash_new_syp"' in source
    assert '"shamcash_syp": "shamcash_new_syp"' in source
    assert '"shamcash_new_syp": "shamcash_new_syp"' in source
    assert '"shamcash_new.syp": "shamcash_new_syp"' in source
    assert "_CALLBACK_PATTERN" in source
    assert "_CODE_ALIASES" in source


def test_legacy_payment_method_router_does_not_capture_setup_confirmation():
    source = (ROOT / "handlers/payment_method_legacy_compat.py").read_text(encoding="utf-8")
    assert "(?!confirm$)" in source
    assert 'admin_pm_setup_confirm' not in source.split("@router.callback_query", 1)[1].split("async def", 1)[0]


def test_legacy_payment_method_callback_delegates_to_canonical_state_change():
    source = (ROOT / "handlers/payment_method_legacy_compat.py").read_text(encoding="utf-8")
    assert "_set_payment_method_enabled" in source
    assert "payment_method_enable_legacy_callback" in source
    assert "payment_method_disable_legacy_callback" in source
    assert "payment_method_toggle_legacy_callback" in source


def test_old_payment_method_router_is_not_in_dispatcher():
    bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "payment_method_setup_policy" in bot_source
    assert "payment_methods.router" not in bot_source
