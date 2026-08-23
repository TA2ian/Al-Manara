from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verification_pending_policy_is_registered_before_verification():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "verification_pending_policy" in source
    assert source.index("dp.include_router(verification_pending_policy.router)") < source.index("dp.include_router(verification_policy.router)")


def test_legacy_verification_pending_guard_is_removed():
    assert not (ROOT / "handlers" / "verification_pending_guard.py").exists()


def test_pending_policy_blocks_duplicate_verification_submission():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert 'status == "pending"' in source
    assert "لا تحتاج إلى إعادة إرسالها" in source
    assert "raise SkipHandler" in source


def test_pending_policy_has_no_retired_qr_submission_delegate():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert "waiting_shamcash_qr" not in source
    assert "handlers.verification" not in source
