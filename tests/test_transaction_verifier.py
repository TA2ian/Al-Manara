from decimal import Decimal

import pytest

import services.transaction_verifier as verifier
from services.transaction_verifier import (
    EVM_NETWORKS,
    EXPLORERS,
    SOLANA_USDT_MINT,
    SUPPORTED_NETWORKS,
    TRANSFER_TOPIC,
    USDT_CONTRACTS,
    TransactionVerification,
    _normalize_network,
    _txid_valid,
    verify_transaction,
)


@pytest.mark.parametrize(
    ("network", "txid", "expected"),
    [
        ("ETH", "0x" + "a" * 64, True),
        ("BEP20", "0x" + "b" * 64, True),
        ("ARB", "0x" + "c" * 64, True),
        ("POLYGON", "0x" + "d" * 64, True),
        ("TRC20", "e" * 64, True),
        ("SOLANA", "5Pj5fCupXLUePYn18JkY8SrRaWFiUctuDTRwvUy2ML9yvkENLb1QMYbcBGcBXRrSVDjp7RjUwk9a3rLC6gpvtYpZ", True),
        ("ETH", "a" * 64, False),
        ("TRC20", "0x" + "e" * 64, False),
        ("SOLANA", "0" * 40, False),
    ],
)
def test_transaction_id_shape_is_network_specific(network, txid, expected):
    assert _txid_valid(network, txid) is expected


def test_network_aliases_are_canonicalized():
    assert _normalize_network("ERC20") == "ETH"
    assert _normalize_network("Ethereum") == "ETH"
    assert _normalize_network("Arbitrum") == "ARB"
    assert _normalize_network("MATIC") == "POLYGON"


def test_usdt_contract_and_explorer_registry_covers_every_supported_network():
    assert SUPPORTED_NETWORKS == set(USDT_CONTRACTS) | {"TRC20", "SOLANA"}
    assert set(EXPLORERS) == SUPPORTED_NETWORKS
    assert SOLANA_USDT_MINT.startswith("Es9v")
    assert TRANSFER_TOPIC == "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a9df523b3ef"
    assert EVM_NETWORKS == set(USDT_CONTRACTS)


def test_evm_confirmation_policy_has_safe_default(monkeypatch):
    monkeypatch.delenv("ALMANARA_EVM_MIN_CONFIRMATIONS", raising=False)
    monkeypatch.delenv("ALMANARA_EVM_CONFIRMATIONS_ETH", raising=False)
    assert verifier._evm_required_confirmations("ETH") == 3


def test_evm_confirmation_policy_supports_network_override(monkeypatch):
    monkeypatch.setenv("ALMANARA_EVM_MIN_CONFIRMATIONS", "5")
    monkeypatch.setenv("ALMANARA_EVM_CONFIRMATIONS_ETH", "7")
    assert verifier._evm_required_confirmations("ETH") == 7
    assert verifier._evm_required_confirmations("ARB") == 5


def test_evm_confirmation_policy_rejects_invalid_values(monkeypatch):
    monkeypatch.setenv("ALMANARA_EVM_MIN_CONFIRMATIONS", "0")
    with pytest.raises(ValueError, match="between 1 and 10000"):
        verifier._evm_required_confirmations("ETH")


@pytest.mark.asyncio
@pytest.mark.parametrize("network", sorted(EVM_NETWORKS))
async def test_evm_verifier_accepts_exact_usdt_transfer_after_required_confirmations(monkeypatch, network):
    recipient = "0x" + "12" * 20
    txid = "0x" + "ab" * 32
    padded_recipient = "0x" + "0" * 24 + recipient[2:]
    receipt = {
        "status": "0x1",
        "blockNumber": "0x10",
        "logs": [
            {
                "address": USDT_CONTRACTS[network],
                "topics": ["0x" + TRANSFER_TOPIC, "0x" + "0" * 64, padded_recipient],
                "data": hex(25 * 10**6),
            }
        ],
    }

    async def fake_post(session, url, payload):
        if payload["method"] == "eth_getTransactionReceipt":
            return {"result": receipt}
        return {"result": "0x12"}

    monkeypatch.setattr(verifier, "_post_json", fake_post)
    result = await verifier._verify_evm(network, txid, recipient, Decimal("25"))
    assert result.verified is True
    assert result.confirmed is True
    assert result.asset_verified is True
    assert result.recipient_verified is True
    assert result.amount_verified is True


@pytest.mark.asyncio
async def test_evm_verifier_rejects_exact_transfer_until_confirmation_threshold(monkeypatch):
    network = "ETH"
    recipient = "0x" + "12" * 20
    txid = "0x" + "ab" * 32
    receipt = {
        "status": "0x1",
        "blockNumber": "0x10",
        "logs": [{
            "address": USDT_CONTRACTS[network],
            "topics": ["0x" + TRANSFER_TOPIC, "0x" + "0" * 64, "0x" + "0" * 24 + recipient[2:]],
            "data": hex(25 * 10**6),
        }],
    }

    async def fake_post(session, url, payload):
        return {"result": receipt if payload["method"] == "eth_getTransactionReceipt" else "0x11"}

    monkeypatch.setattr(verifier, "_post_json", fake_post)
    result = await verifier._verify_evm(network, txid, recipient, Decimal("25"))
    assert result.verified is False
    assert result.confirmed is False
    assert result.asset_verified is True
    assert result.recipient_verified is True
    assert result.amount_verified is True
    assert result.reason == "USDT transfer is awaiting confirmations (2/3)"


@pytest.mark.asyncio
async def test_evm_verifier_rejects_wrong_amount(monkeypatch):
    network = "ETH"
    recipient = "0x" + "34" * 20
    txid = "0x" + "cd" * 32
    receipt = {
        "status": "0x1",
        "blockNumber": "0x10",
        "logs": [
            {
                "address": USDT_CONTRACTS[network],
                "topics": ["0x" + TRANSFER_TOPIC, "0x" + "0" * 64, "0x" + "0" * 24 + recipient[2:]],
                "data": hex(24 * 10**6),
            }
        ],
    }

    async def fake_post(session, url, payload):
        return {"result": receipt if payload["method"] == "eth_getTransactionReceipt" else "0x12"}

    monkeypatch.setattr(verifier, "_post_json", fake_post)
    result = await verifier._verify_evm(network, txid, recipient, Decimal("25"))
    assert result.verified is False
    assert result.recipient_verified is True
    assert result.amount_verified is False


@pytest.mark.asyncio
async def test_tron_verifier_accepts_confirmed_exact_transfer(monkeypatch):
    txid = "ab" * 32
    recipient = "TQh9zR2sQ9uQ6tRjZ8Hf5sYw8kY1J2m3n4"

    async def fake_post(session, url, payload):
        return {"id": txid, "blockNumber": 100, "result": "SUCCESS"}

    async def fake_get(session, url):
        return {
            "data": [{
                "event_name": "Transfer",
                "contract_address": verifier.TRON_USDT_CONTRACT,
                "result": {"to": recipient, "value": str(25 * 10**6)},
            }]
        }

    monkeypatch.setattr(verifier, "_post_json", fake_post)
    monkeypatch.setattr(verifier, "_get_json", fake_get)
    result = await verifier._verify_tron(txid, recipient, Decimal("25"))
    assert result.verified is True
    assert result.confirmed is True
    assert result.amount_verified is True


@pytest.mark.asyncio
async def test_solana_verifier_accepts_finalized_exact_balance_increase(monkeypatch):
    txid = "5Pj5fCupXLUePYn18JkY8SrRaWFiUctuDTRwvUy2ML9yvkENLb1QMYbcBGcBXRrSVDjp7RjUwk9a3rLC6gpvtYpZ"
    recipient = "9xQeWvG816bUx9EPfQ8g4fY4o8qQvM4p7qH5oY4m5sQ"

    async def fake_post(session, url, payload):
        return {
            "result": {
                "meta": {
                    "err": None,
                    "preTokenBalances": [{
                        "accountIndex": 7,
                        "mint": verifier.SOLANA_USDT_MINT,
                        "owner": recipient,
                        "uiTokenAmount": {"amount": "1000000"},
                    }],
                    "postTokenBalances": [{
                        "accountIndex": 7,
                        "mint": verifier.SOLANA_USDT_MINT,
                        "owner": recipient,
                        "uiTokenAmount": {"amount": "26000000"},
                    }],
                }
            }
        }

    monkeypatch.setattr(verifier, "_post_json", fake_post)
    result = await verifier._verify_solana(txid, recipient, Decimal("25"))
    assert result.verified is True
    assert result.confirmed is True
    assert result.amount_verified is True


@pytest.mark.asyncio
async def test_verify_transaction_rejects_invalid_input_without_network_call():
    result = await verify_transaction("ETH", "not-a-txid", "0x" + "1" * 40, Decimal("25"))
    assert result.verified is False
    assert result.reason == "Invalid transaction ID format"


@pytest.mark.asyncio
async def test_verify_transaction_rejects_unsupported_network_without_network_call():
    result = await verify_transaction("TON", "a" * 64, "address", Decimal("25"))
    assert result.verified is False
    assert result.reason == "Unsupported network"


@pytest.mark.asyncio
async def test_verify_transaction_rejects_non_positive_amount_without_network_call():
    result = await verify_transaction("ETH", "0x" + "a" * 64, "0x" + "1" * 40, Decimal("0"))
    assert result.verified is False
    assert result.reason == "Expected amount must be positive"


@pytest.mark.asyncio
async def test_verification_result_exposes_fail_closed_status():
    result = TransactionVerification(
        verified=False,
        network="ETH",
        txid="0x" + "a" * 64,
        recipient="0x" + "1" * 40,
        expected_amount=Decimal("10"),
        reason="network unavailable",
    )
    assert result.status == "rejected"
