"""Regression coverage for customer legal policy navigation."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legal_navigation_router_is_registered_before_legacy_disclaimer_handler():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    legal_router = source.index("dp.include_router(legal_navigation_policy.router)")
    customer_navigation = source.index("dp.include_router(customer_navigation_policy.router)")
    assert legal_router < customer_navigation


def test_legal_navigation_exposes_all_canonical_sections():
    source = (ROOT / "handlers/legal_navigation_policy.py").read_text(encoding="utf-8")
    assert 'callback_data=f"legal_section_{index + 1}"' in source
    assert 'callback_data=f"legal_section_{index}"' in source
    assert 'callback_data=f"legal_section_{index + 2}"' in source
    assert 'r"^legal_section_[1-6]$"' in source
    assert "الشروط والسياسات" in source
    assert "Terms & Policies" in source


def test_legal_navigation_uses_canonical_policy_source():
    source = (ROOT / "handlers/legal_navigation_policy.py").read_text(encoding="utf-8")
    assert "from services.legal_policy import TERMS_TEXT" in source
    assert "from services.locale_service import locale_service" in source
    assert "menu_disclaimer" in source


def test_legacy_monolithic_disclaimer_remains_fallback_only():
    source = (ROOT / "handlers/customer_navigation_policy.py").read_text(encoding="utf-8")
    assert '@router.callback_query(F.data == "menu_disclaimer")' in source
    assert 'locale_service.get(' in source
