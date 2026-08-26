from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_order_wallet_qr_guard_is_embedded_in_canonical_wallet_flow():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    wallets = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
    assert "order_wallet_qr_policy" not in bot
    assert "WalletStates.waiting_qr" in wallets
    assert "return_to_order" in wallets


def test_order_context_qr_skip_is_blocked_by_canonical_wallet_flow():
    source = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
    assert "wallet_qr_skip_prompt" in source
    assert "wallet_qr_skip_confirm" in source
    assert "Verification cannot be skipped during order creation." in source or "لا يمكن تخطي التحقق أثناء إنشاء الطلب." in source
