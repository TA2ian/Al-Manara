from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_database_enforces_one_active_default_wallet_per_user():
    source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "uq_saved_addresses_one_default" in source
    assert "deleted_at IS NULL AND is_default = TRUE" in source


def test_saved_wallet_order_selection_requires_verified_qr_backed_entry():
    source = (ROOT / "handlers/saved_wallets.py").read_text(encoding="utf-8")
    assert "verification_status = 'verified'" in source
    assert "qr_photo_id IS NOT NULL" in source
    assert "OrderStates.waiting_currency" in source
