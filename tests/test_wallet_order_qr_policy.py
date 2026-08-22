from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_order_wallet_qr_guard_precedes_wallet_registry():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert bot.index("dp.include_router(order_wallet_qr_policy.router)") < bot.index("dp.include_router(wallets.router)")


def test_order_context_qr_skip_is_blocked():
    source = (ROOT / "handlers" / "order_wallet_qr_policy.py").read_text(encoding="utf-8")
    assert "wallet_qr_skip_prompt" in source
    assert "wallet_qr_skip_confirm" in source
    assert "return_to_order" in source
