from services.shamcash_qr_validator import qr_matches_account


def test_exact_shamcash_account_matches_qr():
    assert qr_matches_account("shamcash-12345", "shamcash-12345")


def test_whitespace_and_prefix_are_normalized():
    assert qr_matches_account("SHAM12345", "account: SHAM12345")


def test_query_parameter_can_match_account():
    assert qr_matches_account("0933000000", "https://example.invalid/pay?account=0933000000")


def test_wrong_account_does_not_match():
    assert not qr_matches_account("0933000000", "0933111111")
