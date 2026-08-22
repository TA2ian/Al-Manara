"""Regression checks for atomic receipt callback routing."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_receipt_transition_policy_is_registered_before_legacy_receipt_handler():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    transition_pos = bot.index("dp.include_router(receipt_transition_policy.router)")
    legacy_pos = bot.index("dp.include_router(my_orders.router)")
    assert transition_pos < legacy_pos


def test_receipt_transition_policy_uses_atomic_order_transition():
    source = (ROOT / "handlers" / "receipt_transition_policy.py").read_text(encoding="utf-8")
    assert "transition_order(" in source
    assert '"receipt_received"' in source
    assert 'F.data.startswith("retry_receipt_")' in source
    assert 'F.data.startswith("manual_review_")' in source


def test_receipt_transition_policy_checks_order_ownership():
    source = (ROOT / "handlers" / "receipt_transition_policy.py").read_text(encoding="utf-8")
    assert "u.telegram_id = $2" in source
