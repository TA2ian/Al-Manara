"""Regression coverage for the authoritative order confirmation formatter usage."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_order_confirmation_uses_centralized_money_and_usdt_formatters():
    source = (ROOT / "handlers" / "order_confirmation_policy.py").read_text(encoding="utf-8")
    assert "from services.formatters import money, usdt" in source
    assert "usdt(data['amount_usdt'])" in source
    assert "money(calculation['total_amount'])" in source
    assert ":,.3f" not in source
    assert ":,.2f" not in source
