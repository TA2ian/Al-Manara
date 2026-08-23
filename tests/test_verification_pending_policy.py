from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verification_pending_policy_is_registered_before_verification():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "verification_pending_policy" in source
    assert source.index("dp.include_router(verification_pending_policy.router)") < source.index("dp.include_router(verification.router)")


def test_legacy_verification_pending_guard_is_removed():
    assert not (ROOT / "handlers" / "verification_pending_guard.py").exists()


def test_pending_policy_blocks_duplicate_verification_submission():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert 'status == "pending"' in source
    assert "تم استلام بياناتك بالفعل" in source
    assert "لن يسمح النظام بإرسال طلب توثيق آخر" in source
    assert "تم منع إنشاء طلب توثيق ثانٍ" in source
    assert "await state.clear()" in source


def test_pending_policy_delegates_non_pending_qr_to_existing_submission_flow():
    source = (ROOT / "handlers/verification_pending_policy.py").read_text(encoding="utf-8")
    assert "await state.update_data(shamcash_qr_photo_id=message.photo[-1].file_id)" in source
    assert "from handlers.verification import submit_verification" in source
    assert "await submit_verification(message, state)" in source
