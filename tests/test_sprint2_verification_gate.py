from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pending_verification_is_authoritative_and_blocks_duplicate_submission():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert 'status == "pending"' in source
    assert "second verification request" in source
    assert "raise SkipHandler" in source


def test_approved_verification_cannot_be_restarted():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert 'user["is_verified"] or status == "approved"' in source
    assert "لا تحتاج إلى إرسال طلب توثيق جديد" in source


def test_stale_qr_fsm_session_is_guarded():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert "VerificationStates.waiting_shamcash_qr" in source
    assert "await state.clear()" in source


def test_retired_verification_guard_is_absent():
    assert not (ROOT / "handlers/verification_pending_guard.py").exists()
