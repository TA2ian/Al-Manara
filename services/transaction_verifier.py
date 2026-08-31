"""Authoritative on-chain verification for USDT fulfillment transactions."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp


SUPPORTED_NETWORKS = {"BEP20", "TRC20", "ARB", "SOLANA", "ETH", "POLYGON"}
EVM_NETWORKS = {"BEP20", "ARB", "ETH", "POLYGON"}

USDT_CONTRACTS = {
    "ETH": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "BEP20": "0x55d398326f99059ff775485246999027b3197955",
    "ARB": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
    "POLYGON": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
}
TRON_USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
SOLANA_USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
TRANSFER_TOPIC = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a3df6f0f0f"

RPC_DEFAULTS = {
    "ETH": "https://ethereum-rpc.publicnode.com",
    "BEP20": "https://bsc-rpc.publicnode.com",
    "ARB": "https://arbitrum-one-rpc.publicnode.com",
    "POLYGON": "https://polygon-bor-rpc.publicnode.com",
}
EXPLORERS = {
    "ETH": "https://etherscan.io/tx/{}",
    "BEP20": "https://bscscan.com/tx/{}",
    "ARB": "https://arbiscan.io/tx/{}",
    "POLYGON": "https://polygonscan.com/tx/{}",
    "TRC20": "https://tronscan.org/#/transaction/{}",
    "SOLANA": "https://explorer.solana.com/tx/{}",
}


@dataclass(frozen=True)
class TransactionVerification:
    verified: bool
    network: str
    txid: str
    recipient: str
    expected_amount: Decimal
    actual_amount: Decimal | None = None
    confirmed: bool = False
    successful: bool = False
    asset_verified: bool = False
    recipient_verified: bool = False
    amount_verified: bool = False
    reason: str = ""
    explorer_url: str = ""

    @property
    def status(self) -> str:
        return "verified" if self.verified else "rejected"


def _money(value: Decimal | float | int | str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid monetary amount") from exc


def _normalize_network(network: str) -> str:
    value = (network or "").strip().upper()
    aliases = {"ERC20": "ETH", "ETHEREUM": "ETH", "ARBITRUM": "ARB", "MATIC": "POLYGON"}
    return aliases.get(value, value)


def _txid_valid(network: str, txid: str) -> bool:
    value = (txid or "").strip()
    if network in EVM_NETWORKS:
        return bool(re.fullmatch(r"0x[0-9a-fA-F]{64}", value))
    if network == "TRC20":
        return bool(re.fullmatch(r"[0-9a-fA-F]{64}", value))
    if network == "SOLANA":
        return bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,88}", value))
    return False


async def _post_json(session: aiohttp.ClientSession, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with session.post(url, json=payload) as response:
        if response.status != 200:
            raise RuntimeError(f"RPC returned HTTP {response.status}")
        data = await response.json(content_type=None)
        if not isinstance(data, dict):
            raise RuntimeError("RPC returned invalid JSON")
        if data.get("error"):
            raise RuntimeError(str(data["error"]))
        return data


async def _verify_evm(network: str, txid: str, recipient: str, expected: Decimal) -> TransactionVerification:
    endpoint = os.getenv(f"ALMANARA_RPC_{network}", RPC_DEFAULTS[network])
    recipient_normalized = recipient.lower()
    contract = USDT_CONTRACTS[network].lower()
    explorer = EXPLORERS[network].format(txid)

    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        receipt = (await _post_json(session, endpoint, {"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt", "params": [txid]})).get("result")
        if not receipt:
            return TransactionVerification(False, network, txid, recipient, expected, reason="Transaction receipt not found", explorer_url=explorer)
        if receipt.get("status") != "0x1":
            return TransactionVerification(False, network, txid, recipient, expected, confirmed=True, successful=False, reason="Transaction execution failed", explorer_url=explorer)

        block_hex = receipt.get("blockNumber")
        if not block_hex:
            return TransactionVerification(False, network, txid, recipient, expected, successful=True, reason="Transaction has no block", explorer_url=explorer)
        block_number = int(block_hex, 16)
        latest_hex = (await _post_json(session, endpoint, {"jsonrpc": "2.0", "id": 2, "method": "eth_blockNumber", "params": []})).get("result")
        latest = int(latest_hex, 16) if latest_hex else block_number
        confirmed = latest >= block_number

        transfers = []
        for log in receipt.get("logs", []):
            if (log.get("address") or "").lower() != contract:
                continue
            topics = log.get("topics") or []
            if len(topics) < 3 or topics[0].lower().removeprefix("0x") != TRANSFER_TOPIC:
                continue
            to_address = "0x" + topics[2].lower()[-40:]
            try:
                amount = Decimal(int((log.get("data") or "0x0"), 16)) / Decimal(10**6)
            except (ValueError, InvalidOperation):
                continue
            transfers.append((to_address, amount))

        matching = next(((to, amount) for to, amount in transfers if to == recipient_normalized and amount == expected), None)
        if matching is None:
            recipient_match = any(to == recipient_normalized for to, _ in transfers)
            actual = next((amount for to, amount in transfers if to == recipient_normalized), None)
            return TransactionVerification(False, network, txid, recipient, expected, actual_amount=actual, confirmed=confirmed, successful=True, asset_verified=bool(transfers), recipient_verified=recipient_match, reason="No exact USDT transfer to the order wallet", explorer_url=explorer)

        return TransactionVerification(True, network, txid, recipient, expected, actual_amount=matching[1], confirmed=confirmed, successful=True, asset_verified=True, recipient_verified=True, amount_verified=True, reason="Verified USDT transfer", explorer_url=explorer)


async def _verify_tron(txid: str, recipient: str, expected: Decimal) -> TransactionVerification:
    base = os.getenv("ALMANARA_TRON_RPC", "https://api.trongrid.io")
    explorer = EXPLORERS["TRC20"].format(txid)
    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        info = await _post_json(session, f"{base}/walletsolidity/gettransactioninfobyid", {"value": txid})
        if not info.get("id") or not info.get("blockNumber"):
            return TransactionVerification(False, "TRC20", txid, recipient, expected, reason="Transaction is not solidified", explorer_url=explorer)
        if info.get("result") != "SUCCESS":
            return TransactionVerification(False, "TRC20", txid, recipient, expected, confirmed=True, successful=False, reason="TRON transaction failed", explorer_url=explorer)

        events = await _post_json(session, f"{base}/v1/transactions/{txid}/events", {})
        data = events.get("data") or []
        for event in data:
            if event.get("event_name") != "Transfer":
                continue
            if (event.get("contract_address") or "") != TRON_USDT_CONTRACT:
                continue
            result = event.get("result") or {}
            to_address = result.get("to") or result.get("to_address")
            raw_amount = result.get("value") or result.get("amount")
            if not to_address or raw_amount is None:
                continue
            try:
                amount = Decimal(str(raw_amount)) / Decimal(10**6)
            except InvalidOperation:
                continue
            if to_address == recipient and amount == expected:
                return TransactionVerification(True, "TRC20", txid, recipient, expected, actual_amount=amount, confirmed=True, successful=True, asset_verified=True, recipient_verified=True, amount_verified=True, reason="Verified solidified USDT transfer", explorer_url=explorer)

        return TransactionVerification(False, "TRC20", txid, recipient, expected, confirmed=True, successful=True, reason="No exact USDT Transfer event to the order wallet", explorer_url=explorer)


async def _verify_solana(txid: str, recipient: str, expected: Decimal) -> TransactionVerification:
    endpoint = os.getenv("ALMANARA_RPC_SOLANA", "https://api.mainnet-beta.solana.com")
    explorer = EXPLORERS["SOLANA"].format(txid)
    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getTransaction", "params": [txid, {"commitment": "finalized", "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]}
        result = (await _post_json(session, endpoint, payload)).get("result")
        if not result or not result.get("meta"):
            return TransactionVerification(False, "SOLANA", txid, recipient, expected, reason="Finalized transaction not found", explorer_url=explorer)
        if result["meta"].get("err") is not None:
            return TransactionVerification(False, "SOLANA", txid, recipient, expected, confirmed=True, successful=False, reason="Solana transaction failed", explorer_url=explorer)

        post = result["meta"].get("postTokenBalances") or []
        pre = {item.get("accountIndex"): item for item in (result["meta"].get("preTokenBalances") or [])}
        expected_raw = int(expected * Decimal(10**6))
        for balance in post:
            if balance.get("mint") != SOLANA_USDT_MINT or balance.get("owner") != recipient:
                continue
            before = pre.get(balance.get("accountIndex"), {}).get("uiTokenAmount", {}).get("amount", "0")
            after = balance.get("uiTokenAmount", {}).get("amount", "0")
            delta = int(after) - int(before)
            if delta == expected_raw:
                return TransactionVerification(True, "SOLANA", txid, recipient, expected, actual_amount=expected, confirmed=True, successful=True, asset_verified=True, recipient_verified=True, amount_verified=True, reason="Verified finalized USDT token balance increase", explorer_url=explorer)

        return TransactionVerification(False, "SOLANA", txid, recipient, expected, confirmed=True, successful=True, reason="No exact finalized USDT increase for the order wallet", explorer_url=explorer)


async def verify_transaction(network: str, txid: str, recipient: str, expected_amount: Decimal | float | int) -> TransactionVerification:
    normalized = _normalize_network(network)
    expected = _money(expected_amount)
    if normalized not in SUPPORTED_NETWORKS:
        return TransactionVerification(False, normalized, txid, recipient, expected, reason="Unsupported network")
    if expected <= 0:
        return TransactionVerification(False, normalized, txid, recipient, expected, reason="Expected amount must be positive")
    if not _txid_valid(normalized, txid):
        return TransactionVerification(False, normalized, txid, recipient, expected, reason="Invalid transaction ID format", explorer_url=EXPLORERS.get(normalized, "").format(txid))
    if not recipient or not recipient.strip():
        return TransactionVerification(False, normalized, txid, recipient, expected, reason="Missing recipient")
    try:
        if normalized in EVM_NETWORKS:
            return await _verify_evm(normalized, txid.strip(), recipient.strip(), expected)
        if normalized == "TRC20":
            return await _verify_tron(txid.strip(), recipient.strip(), expected)
        return await _verify_solana(txid.strip(), recipient.strip(), expected)
    except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, ValueError) as exc:
        return TransactionVerification(False, normalized, txid, recipient, expected, reason=f"Verification service unavailable: {exc}", explorer_url=EXPLORERS.get(normalized, "").format(txid))
