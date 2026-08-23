from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pending_verification_is_authoritative_and_blocks_duplicate_submission():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert 'status == "pending"' in source
    assert "لا تحتاج إلى إعادة إرسالها" in source
    assert "raise SkipHandler" in source


def test_approved_verification_cannot_be_restarted():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert 'user["is_verified"] or status == "approved"' in source
    assert "لا تحتاج إلى طلب جديد" in source


def test_shamcash_identity_is_one_qr_input_with_optional_matching_caption():
    source = (ROOT / "handlers/verification_policy.py").read_text(encoding="utf-8")
    assert "VerificationStates.waiting_shamcash_identity" in source
    assert "_decode_qr" in source
    assert "caption.casefold() != qr_value.casefold()" in source
    assert "shamcash_address_from_qr=true" in source


def test_retired_verification_surfaces_are_absent():
    assert not (ROOT / "handlers/verification.py").exists()
    assert not (ROOT / "handlers/verification_pending_guard.py").exists()
