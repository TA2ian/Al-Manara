"""Wallet address validation service."""
import re
import logging

logger = logging.getLogger(__name__)


class WalletValidator:
    """Validate cryptocurrency wallet addresses."""

    BEP20_PATTERN = re.compile(r'^0x[a-fA-F0-9]{40}$')
    TRC20_PATTERN = re.compile(r'^T[1-9A-HJ-NP-Za-km-z]{33}$')

    # Burn and blacklisted addresses
    BURN_ADDRESSES = {
        '0x0000000000000000000000000000000000000000',
        '0x000000000000000000000000000000000000dead',
        '0x0000000000000000000000000000000000000001',
    }

    @classmethod
    def validate(cls, address: str, network: str) -> dict:
        """Validate wallet address for given network.

        Returns:
            dict with 'valid', 'network', 'address', 'error', 'warnings'
        """
        address = address.strip()

        if network == 'BEP20':
            return cls._validate_bep20(address)
        elif network == 'TRC20':
            return cls._validate_trc20(address)

        return {'valid': False, 'error': 'Unknown network'}

    @classmethod
    def _validate_bep20(cls, address: str) -> dict:
        """Validate BEP20 address."""
        result = {
            'valid': False,
            'network': 'BEP20',
            'address': address,
            'warnings': []
        }

        if not cls.BEP20_PATTERN.match(address):
            result['error'] = 'Invalid BEP20 address format'
            return result

        if address.lower() in cls.BURN_ADDRESSES:
            result['error'] = 'Burn address not allowed'
            return result

        result['valid'] = True
        return result

    @classmethod
    def _validate_trc20(cls, address: str) -> dict:
        """Validate TRC20 address."""
        result = {
            'valid': False,
            'network': 'TRC20',
            'address': address,
            'warnings': []
        }

        if not cls.TRC20_PATTERN.match(address):
            result['error'] = 'Invalid TRC20 address format'
            return result

        result['valid'] = True
        return result

    @classmethod
    def detect_network(cls, address: str) -> str:
        """Detect network from address."""
        if cls.BEP20_PATTERN.match(address):
            return 'BEP20'
        elif cls.TRC20_PATTERN.match(address):
            return 'TRC20'
        return None
