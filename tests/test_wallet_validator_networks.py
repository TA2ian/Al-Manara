from services.wallet_validator import WalletValidator


def test_supported_networks_are_explicitly_validated():
    assert WalletValidator.validate("0x" + "1" * 40, "BEP20")["valid"]
    assert WalletValidator.validate("0x" + "2" * 40, "ARB")["valid"]
    assert WalletValidator.validate("0x" + "3" * 40, "ETH")["valid"]
    assert WalletValidator.validate("T" + "A" * 33, "TRC20")["valid"]
    assert WalletValidator.validate("UQ" + "A" * 46, "TON")["valid"]
    assert WalletValidator.validate("-1:" + "a" * 64, "TON")["valid"]
    assert WalletValidator.validate("So11111111111111111111111111111111111111112", "SOLANA")["valid"]


def test_network_aliases_are_canonicalized():
    assert WalletValidator.normalize_network("ERC20") == "ETH"
    assert WalletValidator.normalize_network("ARBITRUM") == "ARB"
    assert WalletValidator.normalize_network("SOL") == "SOLANA"


def test_invalid_cross_network_address_is_rejected():
    evm = "0x" + "1" * 40
    assert not WalletValidator.validate(evm, "TON")["valid"]
    assert not WalletValidator.validate(evm, "SOLANA")["valid"]
