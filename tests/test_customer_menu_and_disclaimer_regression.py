"""Regression coverage for customer quick-menu and legal onboarding routing."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_customer_menu_accepts_current_and_legacy_reply_button_variants():
    source = (ROOT / "handlers/customer_settings_policy.py").read_text(encoding="utf-8")
    assert "القائمة ⚙️" in source
    assert "الإعدادات ⚙️" in source
    assert "_normalize_menu_label" in source
    assert "_SUPPORTED_MENU_LABELS" in source


def test_customer_menu_clears_stale_fsm_state():
    source = (ROOT / "handlers/customer_settings_policy.py").read_text(encoding="utf-8")
    assert "FSMContext" in source
    assert "await state.clear()" in source


def test_customer_menu_has_priority_over_state_specific_handlers():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    customer_settings = source.index("dp.include_router(customer_settings_policy.router)")
    order_amount = source.index("dp.include_router(order_amount_policy.router)")
    assert customer_settings < order_amount
    assert source.count("dp.include_router(customer_settings_policy.router)") == 1


def test_disclaimer_uses_canonical_legal_policy_instead_of_stale_locale_copy():
    source = (ROOT / "services/locale_service.py").read_text(encoding="utf-8")
    assert "from services.legal_policy import get_terms_text" in source
    assert 'if key == "terms_text":' in source
    assert "return get_terms_text" in source


def test_start_uses_concise_onboarding_terms():
    source = (ROOT / "handlers/start.py").read_text(encoding="utf-8")
    legal_source = (ROOT / "services/legal_policy.py").read_text(encoding="utf-8")
    assert "get_start_terms_text" in source
    assert "START_TERMS_TEXT" in legal_source
    assert "يمكنك بعد التسجيل الوصول إلى الشروط والسياسات الكاملة" in legal_source


def test_complete_legal_center_has_seven_contextual_sections():
    source = (ROOT / "handlers/legal_navigation_policy.py").read_text(encoding="utf-8")
    legal_source = (ROOT / "services/legal_policy.py").read_text(encoding="utf-8")
    assert "legal_section_[1-7]" in source
    for title in (
        "المحفظة وعنوان الاستلام", "التوثيق والخصوصية", "الطلبات والمعالجة",
        "الأمان ومكافحة الاحتيال", "التحديثات والسجلات",
    ):
        assert title in source or title in legal_source


def test_start_and_disclaimer_share_the_same_legal_policy_owner():
    start_source = (ROOT / "handlers/start.py").read_text(encoding="utf-8")
    legal_source = (ROOT / "services/legal_policy.py").read_text(encoding="utf-8")
    locale_source = (ROOT / "services/locale_service.py").read_text(encoding="utf-8")
    assert "from services.legal_policy import get_start_terms_text" in start_source
    assert "def get_terms_text" in legal_source
    assert "def get_start_terms_text" in legal_source
    assert "from services.legal_policy import get_terms_text" in locale_source


def test_phone_verification_has_one_canonical_runtime_owner():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    verification = source.count("dp.include_router(verification_policy.router)")
    assert verification == 1
    assert "verification_keyboard_cleanup" not in source
    policy = (ROOT / "handlers/verification_policy.py").read_text(encoding="utf-8")
    assert "@router.message(VerificationStates.waiting_phone, F.contact)" in policy
    assert "await _ask_full_name(message, state, lang)" in policy
