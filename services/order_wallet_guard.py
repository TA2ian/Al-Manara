"""Authoritative wallet guard for customer order creation.

Legacy order handlers may still exist, but they must pass this guard before
using a wallet. The order flow must never accept an unverified wallet or an
order-local QR/skip-QR path.
"""

from __future__ import annotations

from typing import Any


class WalletOrderGuardError(ValueError):
    """Raised when a wallet cannot be used for an order."""


def validate_order_wallet(wallet: Any) -> None:
    """Require a registry wallet that is verified and has a stored QR.

    The function intentionally accepts a mapping-like row so it can be used
    with asyncpg records without coupling the policy to database code.
    """
    if wallet is None:
        raise WalletOrderGuardError("wallet_not_found")

    if not bool(wallet.get("is_verified", False)):
        raise WalletOrderGuardError("wallet_not_verified")

    if not wallet.get("wallet_qr_photo_id"):
        raise WalletOrderGuardError("wallet_qr_missing")


def reject_order_local_qr(action: str) -> None:
    """Reject legacy order-local QR actions such as skip/upload."""
    raise WalletOrderGuardError(f"order_local_qr_not_allowed:{action}")
