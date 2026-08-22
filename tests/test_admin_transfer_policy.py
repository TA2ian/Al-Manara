from handlers.admin_transfer_policy import _valid_txid


def test_trc20_txid_shape():
    assert _valid_txid("a" * 64, "TRC20")
    assert not _valid_txid("a" * 63, "TRC20")
    assert not _valid_txid("0x" + "a" * 64, "TRC20")


def test_bep20_txid_shape():
    assert _valid_txid("0x" + "a" * 64, "BEP20")
    assert not _valid_txid("a" * 64, "BEP20")


def test_erc20_txid_shape():
    assert _valid_txid("0x" + "a" * 64, "ERC20")
    assert not _valid_txid("0x" + "a" * 63, "ERC20")


def test_unknown_network_has_conservative_generic_shape():
    assert _valid_txid("A" * 32, "OTHER")
    assert not _valid_txid("short", "OTHER")
