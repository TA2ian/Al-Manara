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


def test_old_payment_method_router_is_not_in_dispatcher():
    bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "payment_method_setup_policy" in bot_source
    assert "payment_methods.router" not in bot_source
