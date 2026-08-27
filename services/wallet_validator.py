"""Wallet address validation service."""
import logging
import re

logger = logging.getLogger(__name__)


class WalletValidator:
    """Validate cryptocurrency wallet addresses for supported USDT networks."""

    BEP20_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
    TRC20_PATTERN = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
    EVM_PATTERN = BEP20_PATTERN
    TON_FRIENDLY_PATTERN = re.compile(r"^[EU][Qq][A-Za-z0-9_-]{46}$")
    TON_RAW_PATTERN = re.compile(r"^(?:0|-1):[0-9a-fA-F]{64}$")
    SOLANA_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

    SUPPORTED_NETWORKS = {"BEP20", "TRC20", "TON", "ARB", "SOLANA", "ETH"}
    NETWORK_ALIASES = {
        "ERC20": "ETH",
        "ETHEREUM": "ETH",
        "ARBITRUM": "ARB",
        "SOL": "SOLANA",
        "SOLANA": "SOLANA",
    }

    BURN_ADDRESSES = {
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead",
        "0x0000000000000000000000000000000000000001",
    }

    @classmethod
    def normalize_network(cls, network: str | None) -> str | None:
        value = (network or "").strip().upper()
        return cls.NETWORK_ALIASES.get(value, value) if value else None

    @classmethod
    def validate(cls, address: str, network: str) -> dict:
        """Validate a wallet address against an explicitly selected network."""
        address = (address or "").strip()
        normalized_network = cls.normalize_network(network)
        if normalized_network == "BEP20":
            return cls._validate_bep20(address)
        if normalized_network == "TRC20":
            return cls._validate_trc20(address)
        if normalized_network in {"ETH", "ARB"}:
            return cls._validate_evm(address, normalized_network)
        if normalized_network == "TON":
            return cls._validate_ton(address)
        if normalized_network == "SOLANA":
            return cls._validate_solana(address)
        return {"valid": False, "network": normalized_network, "address": address, "error": "Unknown network", "warnings": []}

    @classmethod
    def _validate_bep20(cls, address: str) -> dict:
        result = {"valid": False, "network": "BEP20", "address": address, "warnings": []}
        if not cls.BEP20_PATTERN.fullmatch(address):
            result["error"] = "Invalid BEP20 address format"
            return result
        if address.lower() in cls.BURN_ADDRESSES:
            result["error"] = "Burn address not allowed"
            return result
        result["valid"] = True
        return result

    @classmethod
    def _validate_evm(cls, address: str, network: str) -> dict:
        result = {"valid": False, "network": network, "address": address, "warnings": []}
        if not cls.EVM_PATTERN.fullmatch(address):
            result["error"] = f"Invalid {network} address format"
            return result
        if address.lower() in cls.BURN_ADDRESSES:
            result["error"] = "Burn address not allowed"
            return result
        result["valid"] = True
        return result

    @classmethod
    def _validate_trc20(cls, address: str) -> dict:
        result = {"valid": False, "network": "TRC20", "address": address, "warnings": []}
        if not cls.TRC20_PATTERN.fullmatch(address):
            result["error"] = "Invalid TRC20 address format"
            return result
        result["valid"] = True
        return result

    @classmethod
    def _validate_ton(cls, address: str) -> dict:
        result = {"valid": False, "network": "TON", "address": address, "warnings": []}
        if not (cls.TON_FRIENDLY_PATTERN.fullmatch(address) or cls.TON_RAW_PATTERN.fullmatch(address)):
            result["error"] = "Invalid TON address format"
            return result
        result["valid"] = True
        return result

    @classmethod
    def _validate_solana(cls, address: str) -> dict:
        result = {"valid": False, "network": "SOLANA", "address": address, "warnings": []}
        if not cls.SOLANA_PATTERN.fullmatch(address):
            result["error"] = "Invalid Solana address format"
            return result
        result["valid"] = True
        return result

    @classmethod
    def detect_network(cls, address: str, preferred_network: str | None = None) -> str | None:
        """Detect a unique network, or honor an explicit network selected by the user."""
        address = (address or "").strip()
        preferred = cls.normalize_network(preferred_network)
        if preferred:
            return preferred if cls.validate(address, preferred).get("valid") else None
        if cls.TRC20_PATTERN.fullmatch(address):
            return "TRC20"
        if cls.TON_FRIENDLY_PATTERN.fullmatch(address) or cls.TON_RAW_PATTERN.fullmatch(address):
            return "TON"
        if cls.SOLANA_PATTERN.fullmatch(address):
            return "SOLANA"
        if cls.BEP20_PATTERN.fullmatch(address):
            return "BEP20"
        return None
