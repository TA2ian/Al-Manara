from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_qr_first_is_owned_by_canonical_wallet_registry():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    wallets = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
    assert "wallet_qr_first_policy" not in source
    assert "dp.include_router(wallets.router)" in source
    assert "@router.message(WalletStates.waiting_address, F.photo)" in wallets


def test_qr_first_accepts_qr_and_optional_matching_caption():
    source = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
    assert "WalletStates.waiting_address, F.photo" in source
    assert "_decode_qr" in source
    assert "message.caption" in source
    assert "does not match" in source or "لا يطابق" in source
    assert "wallet_qr_photo_id" in source
    assert "wallet_qr_first" in source


def test_existing_address_first_flow_remains_available():
    source = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
    assert "@router.message(WalletStates.waiting_address)" in source
    assert "@router.message(WalletStates.waiting_qr, F.photo)" in source
