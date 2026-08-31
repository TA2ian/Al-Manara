"""Authoritative on-chain verification for USDT fulfillment transactions."""
from __future__ import annotations

import asyncio
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
SOLANA_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TRANSFER_TOPIC = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a9df523b3ef"

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
DEFAULT_EVM_CONFIRMATIONS = 3


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


def _evm_required_confirmations(network: str) -> int:
    raw = os.getenv(f"ALMANARA_EVM_CONFIRMATIONS_{network}")
    if raw is None:
        raw = os.getenv("ALMANARA_EVM_MIN_CONFIRMATIONS")
    if raw is None:
        return DEFAULT_EVM_CONFIRMATIONS
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid EVM confirmation policy") from exc
    if value < 1 or value > 10000:
        raise ValueError("EVM confirmation policy must be between 1 and 10000")
    return value


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


async def _get_json(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    async with session.get(url) as response:
        if response.status != 200:
            raise RuntimeError(f"RPC returned HTTP {response.status}")
        data = await response.json(content_type=None)
        if not isinstance(data, dict):
            raise RuntimeError("RPC returned invalid JSON")
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
        required_confirmations = _evm_required_confirmations(network)
        confirmations = max(0, latest - block_number + 1)
        confirmed = confirmations >= required_confirmations

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
            if to_address == recipient_normalized:
                if amount != expected:
                    return TransactionVerification(False, network, txid, recipient, expected, actual_amount=amount, confirmed=confirmed, successful=True, asset_verified=True, recipient_verified=True, reason="USDT transfer amount does not match the order", explorer_url=explorer)
                if not confirmed:
                    return TransactionVerification(False, network, txid, recipient, expected, actual_amount=amount, confirmed=False, successful=True, asset_verified=True, recipient_verified=True, amount_verified=True, reason=f"USDT transfer is awaiting confirmations ({confirmations}/{required_confirmations})", explorer_url=explorer)
                return TransactionVerification(True, network, txid, recipient, expected, actual_amount=amount, confirmed=True, successful=True, asset_verified=True, recipient_verified=True, amount_verified=True, reason="Verified confirmed USDT transfer", explorer_url=explorer)

        return TransactionVerification(False, network, txid, recipient, expected, confirmed=confirmed, successful=True, reason="No USDT transfer to the order wallet", explorer_url=explorer)


async def _verify_tron(txid: str, recipient: str, expected: Decimal) -> TransactionVerification:
    base = os.getenv("ALMANARA_TRON_RPC", "https://api.trongrid.io").rstrip("/")
    explorer = EXPLORERS["TRC20"].format(txid)
    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        info = await _post_json(session, f"{base}/walletsolidity/gettransactioninfobyid", {"value": txid})
        if not info.get("id") or not info.get("blockNumber"):
            return TransactionVerification(False, "TRC20", txid, recipient, expected, reason="Transaction is not solidified", explorer_url=explorer)
        if info.get("result") != "SUCCESS":
            return TransactionVerification(False, "TRC20", txid, recipient, expected, confirmed=True, successful=False, reason="TRON transaction failed", explorer_url=explorer)

        events = await _get_json(session, f"{base}/v1/transactions/{txid}/events?only_confirmed=true&event_name=Transfer&limit=200")
        for event in events.get("data") or []:
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
            if to_address == recipient:
                if amount == expected:
                    return TransactionVerification(True, "TRC20", txid, recipient, expected, actual_amount=amount, confirmed=True, successful=True, asset_verified=True, recipient_verified=True, amount_verified=True, reason="Verified solidified USDT transfer", explorer_url=explorer)
                return TransactionVerification(False, "TRC20", txid, recipient, expected, actual_amount=amount, confirmed=True, successful=True, asset_verified=True, recipient_verified=True, reason="USDT transfer amount does not match the order", explorer_url=explorer)

        return TransactionVerification(False, "TRC20", txid, recipient, expected, confirmed=True, successful=True, reason="No confirmed USDT Transfer event to the order wallet", explorer_url=explorer)


def _solana_account_key(account_keys: list[Any], account_index: int | None) -> str:
    if account_index is None or account_index < 0 or account_index >= len(account_keys):
        return ""
    account = account_keys[account_index]
    if isinstance(account, str):
        return account
    if isinstance(account, dict):
        return str(account.get("pubkey") or "")
    return ""


def _solana_instruction_transfers(result: dict[str, Any]) -> list[dict[str, str]]:
    transaction = result.get("transaction") or {}
    message = transaction.get("message") or {}
    account_keys = message.get("accountKeys") or []
    instructions: list[Any] = list(message.get("instructions") or [])
    meta = result.get("meta") or {}
    for group in meta.get("innerInstructions") or []:
        instructions.extend(group.get("instructions") or [])

    transfers: list[dict[str, str]] = []
    for instruction in instructions:
        if not isinstance(instruction, dict):
            continue
        if instruction.get("programId") != SOLANA_TOKEN_PROGRAM_ID:
            continue
        parsed = instruction.get("parsed")
        if not isinstance(parsed, dict):
            continue
        if parsed.get("type") not in {"transfer", "transferChecked"}:
            continue
        info = parsed.get("info")
        if not isinstance(info, dict):
            continue
        mint = str(info.get("mint") or "")
        destination = str(info.get("destination") or "")
        raw_amount = info.get("amount")
        if raw_amount is None:
            token_amount = info.get("tokenAmount")
            if isinstance(token_amount, dict):
                raw_amount = token_amount.get("amount")
        if not mint or not destination or raw_amount is None:
            continue
        try:
            amount = str(int(str(raw_amount)))
        except (TypeError, ValueError):
            continue
        transfers.append({"mint": mint, "destination": destination, "amount": amount})

    return transfers


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
        transfers = _solana_instruction_transfers(result)
        account_keys = ((result.get("transaction") or {}).get("message") or {}).get("accountKeys") or []

        for balance in post:
            if balance.get("mint") != SOLANA_USDT_MINT or balance.get("owner") != recipient:
                continue
            account_index = balance.get("accountIndex")
            destination = _solana_account_key(account_keys, account_index)
            before = pre.get(account_index, {}).get("uiTokenAmount", {}).get("amount", "0")
            after = balance.get("uiTokenAmount", {}).get("amount", "0")
            try:
                delta = int(after) - int(before)
            except (TypeError, ValueError):
                continue
            if delta != expected_raw:
                continue
            if not any(
                transfer["mint"] == SOLANA_USDT_MINT
                and transfer["destination"] == destination
                and transfer["amount"] == str(expected_raw)
                for transfer in transfers
            ):
                continue
            return TransactionVerification(True, "SOLANA", txid, recipient, expected, actual_amount=expected, confirmed=True, successful=True, asset_verified=True, recipient_verified=True, amount_verified=True, reason="Verified finalized USDT transfer instruction", explorer_url=explorer)

        return TransactionVerification(False, "SOLANA", txid, recipient, expected, confirmed=True, successful=True, reason="No exact finalized USDT transfer instruction to the order wallet", explorer_url=explorer)


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
