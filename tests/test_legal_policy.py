from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_onboarding_uses_canonical_legal_policy_not_legacy_locale_terms():
    source = (ROOT / "handlers/start.py").read_text(encoding="utf-8")
    assert "from services.legal_policy import get_terms_text" in source
    assert "get_terms_text(lang, Config.PAYMENT_TIMEOUT)" in source
    assert "locale_service.get('terms_text'" not in source


def test_canonical_privacy_policy_limits_verification_data_use():
    source = (ROOT / "services/legal_policy.py").read_text(encoding="utf-8")
    assert "الإجراءات القانونية اللازمة عند وجود احتيال" in source
    assert "لا نستخدم بيانات التوثيق لأغراض تسويقية" in source
    assert "لا يعني طلب حذف الحساب حذف السجلات" in source
    assert "Necessary legal procedures in cases of fraud" in source
