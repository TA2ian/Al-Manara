from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_qr_first_router_precedes_wallet_address_handler():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "wallet_qr_first_policy" in source
    assert source.index("dp.include_router(wallet_qr_first_policy.router)") < source.index("dp.include_router(wallets.router)")


def test_qr_first_accepts_qr_and_optional_matching_caption():
    source = (ROOT / "handlers/wallet_qr_first_policy.py").read_text(encoding="utf-8")
    assert "WalletStates.waiting_address" in source
    assert "qr_decode" in source
    assert "message.caption" in source
    assert "does not match" in source or "لا يطابق" in source
    assert "wallet_qr_photo_id" in source
    assert "wallet_qr_first" in source


def test_existing_address_first_flow_remains_available():
    source = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
    assert "@router.message(WalletStates.waiting_address)" in source
    assert "@router.message(WalletStates.waiting_qr, F.photo)" in source
