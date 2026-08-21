import unittest

from services.order_wallet_guard import (
    WalletOrderGuardError,
    reject_order_local_qr,
    validate_order_wallet,
)


class OrderWalletGuardTests(unittest.TestCase):
    def test_verified_registry_wallet_with_qr_is_allowed(self):
        validate_order_wallet({"is_verified": True, "wallet_qr_photo_id": "qr-1"})

    def test_unverified_wallet_is_rejected(self):
        with self.assertRaisesRegex(WalletOrderGuardError, "wallet_not_verified"):
            validate_order_wallet({"is_verified": False, "wallet_qr_photo_id": "qr-1"})

    def test_missing_qr_is_rejected(self):
        with self.assertRaisesRegex(WalletOrderGuardError, "wallet_qr_missing"):
            validate_order_wallet({"is_verified": True, "wallet_qr_photo_id": None})

    def test_legacy_local_qr_actions_are_rejected(self):
        for action in ("skip", "upload"):
            with self.assertRaisesRegex(WalletOrderGuardError, "order_local_qr_not_allowed"):
                reject_order_local_qr(action)


if __name__ == "__main__":
    unittest.main()
