from decimal import Decimal

import pytest

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
