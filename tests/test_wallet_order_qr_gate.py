from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_currency_flow_blocks_qr_skipped_order_sessions():
    source = (ROOT / "handlers" / "payment_currency_policy.py").read_text(encoding="utf-8")
    assert "wallet_qr_skipped" in source
    assert "WalletStates.waiting_qr" in source
    assert "purchase order cannot be created without a matching stored wallet QR" in source


def test_database_wallet_guard_requires_stored_qr_for_new_orders():
    source = (ROOT / "database_wallet_guards.py").read_text(encoding="utf-8")
    assert "verified order wallet must have a stored QR" in source
    assert "order wallet QR does not match the verified saved wallet" in source
