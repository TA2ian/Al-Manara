import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_locale(lang):
    with (ROOT / "locales" / f"{lang}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def test_locales_use_new_syp_and_current_verification_flow():
    for lang in ("ar", "en"):
        locale = load_locale(lang)
        assert "NEW.SYP" in locale["syp"]
        assert "NEW.SYP" in locale["current_rate"]
        assert "optional" not in locale["upload_shamcash_qr"].lower()
        assert "cannot" in locale["upload_shamcash_qr"].lower() or "لا يمكن" in locale["upload_shamcash_qr"]
        assert "QR" in locale["verification_prompt"]


def test_locale_service_does_not_override_json_values():
    from services.locale_service import locale_service

    ar = load_locale("ar")
    en = load_locale("en")
    assert locale_service.get("enter_amount", "ar") == ar["enter_amount"]
    assert locale_service.get("enter_amount_custom", "ar", min=10, max=100) == ar["enter_amount_custom"].format(min=10, max=100)
    assert locale_service.get("invalid_amount", "en", min=10, max=100) == en["invalid_amount"].format(min=10, max=100)
