from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retired_wallet_order_save_path_is_removed():
    states = (ROOT / "states.py").read_text(encoding="utf-8")
    saved_wallets = (ROOT / "handlers/saved_wallets.py").read_text(encoding="utf-8")

    assert "waiting_save_address" not in states
    assert "waiting_address_label" not in states
    assert "save_address_yes" not in saved_wallets
    assert "save_wallet_with_qr" not in saved_wallets


def test_saved_wallet_router_only_selects_verified_registry_entries():
    source = (ROOT / "handlers/saved_wallets.py").read_text(encoding="utf-8")

    assert "verification_status = 'verified'" in source
    assert "qr_photo_id IS NOT NULL" in source
    assert "saved_address_id" in source
    assert "OrderStates.waiting_currency" in source
