"""Regression coverage for the canonical language-switching router."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_language_policy_is_registered_and_owns_language_entrypoints():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    policy = (ROOT / "handlers/language_policy.py").read_text(encoding="utf-8")
    assert "dp.include_router(language_policy.router)" in bot
    assert '@router.message(F.text.in_(["/language", "/lang"]))' in policy
    assert '@router.callback_query(F.data == "quick_change_lang")' in policy
    assert 'F.data.startswith("policy_set_lang_")' in policy
