from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_profile_distinguishes_unsubmitted_user_from_pending_review():
    source = (ROOT / "handlers/profile.py").read_text(encoding="utf-8")
    assert "has_submitted_verification" in source
    assert "غير موثق بعد" in source
    assert "start_verification_keyboard(lang)" in source


def test_new_user_terms_acceptance_sets_not_verified():
    source = (ROOT / "handlers/start.py").read_text(encoding="utf-8")
    assert "verification_status)" in source
    assert "'not_verified'" in source
    assert "verification_status = CASE" in source


def test_verification_submission_still_notifies_admins():
    source = (ROOT / "handlers/verification.py").read_text(encoding="utf-8")
    assert "verification_status='pending'" in source
    assert "for admin_id in Config.ADMIN_IDS" in source
    assert "طلب توثيق جديد" in source
