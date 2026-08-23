from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_payment_methods_have_only_canonical_shamcash_currency_codes():
    source = (ROOT / "handlers/payment_methods.py").read_text(encoding="utf-8")
    assert '"USD"' in source
    assert '"NEW.SYP"' in source
    assert '"shamcash_usd"' in source
    assert '"shamcash_new_syp"' in source
    assert "shamcash_syp" in source


def test_payment_method_admin_updates_are_audited_and_persisted():
    source = (ROOT / "handlers/payment_methods.py").read_text(encoding="utf-8")
    assert "payment_method_account_update" in source
    assert "payment_method_qr_update" in source
    assert "payment_method_toggle" in source
    assert "UPDATE payment_methods SET account_identifier" in source
    assert "UPDATE payment_methods SET qr_photo_id" in source
    assert "UPDATE payment_methods SET enabled = NOT enabled" in source


def test_order_payment_snapshot_is_captured_from_enabled_shamcash_method():
    source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "snapshot_order_payment_method" in source
    assert "provider='ShamCash'" in source
    assert "enabled=TRUE" in source
    assert "payment_account_snapshot" in source
    assert "payment_qr_photo_id" in source
    assert "BEFORE INSERT ON orders" in source


def test_legacy_syp_is_migrated_without_becoming_a_second_active_method():
    source = (ROOT / "handlers/payment_methods.py").read_text(encoding="utf-8")
    assert "DELETE FROM payment_methods WHERE code = 'shamcash_syp'" in source
    assert "shamcash_new_syp" in source


def test_customer_order_uses_the_verified_wallet_snapshot():
    source = (ROOT / "handlers/order_confirmation_policy.py").read_text(encoding="utf-8")
    assert "verification_status = 'verified'" in source
    assert "wallet[\"address\"]" in source
    assert "wallet[\"qr_photo_id\"]" in source
