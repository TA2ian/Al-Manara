"""Regression coverage for admin destructive/rejection actions and wallet UX."""
import inspect

from handlers import admin_rejection_policy, admin_user_management_policy, verification_admin_policy, wallets
from keyboards.inline import order_admin_keyboard
from keyboards.wallet import SUPPORTED_WALLET_NETWORKS, wallet_network_keyboard


def _callbacks(keyboard):
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_verification_review_exposes_reject_and_confirm_flow():
    source = inspect.getsource(verification_admin_policy)
    assert 'callback_data=f"verify_reject_{telegram_id}"' in source
    assert 'callback_data=f"verify_reject_confirm_{telegram_id}"' in source
    assert "verification_status='rejected'" in source
    assert "is_verified=FALSE" in source


def test_customer_search_exposes_delete_action_and_execute_path():
    source = inspect.getsource(admin_user_management_policy)
    assert 'callback_data=f"admin_del_user_{telegram_id}"' in source
    assert 'callback_data=f"admin_del_confirm_{telegram_id}"' in source
    assert 'DELETE FROM users WHERE id = $1' in source
    assert "action, details, severity" in source


def test_order_rejection_is_exposed_only_for_rejectable_order_views():
    for status in ("pending", "waiting_payment", "receipt_received"):
        callbacks = _callbacks(order_admin_keyboard(123, status))
        assert "admin_reject_123" in callbacks
    payment_confirmed_callbacks = _callbacks(order_admin_keyboard(123, "payment_confirmed"))
    assert "admin_reject_123" not in payment_confirmed_callbacks
    assert "admin_send_usdt_123" in payment_confirmed_callbacks


def test_order_rejection_uses_authoritative_transition_and_preserves_wallet_snapshot():
    source = inspect.getsource(admin_rejection_policy.reject_order)
    assert "transition_order" in source
    assert '"rejected"' in source
    assert "admin_id=callback.from_user.id" in source
    assert '"receipt_photo_id": None' in source
    assert '"wallet_qr_photo_id": None' not in source


def test_wallet_registration_supports_all_networks_and_supported_inputs():
    source = inspect.getsource(wallets._network_prompt)
    assert "العنوان" in source
    assert "صورة" in source
    assert "مشاركة المحفظة مباشرة" in source
    assert "العنوان مع QR" in source
    assert "اختر شبكة USDT" in source
    assert set(SUPPORTED_WALLET_NETWORKS) == {"BEP20", "TRC20", "ARB", "SOLANA", "ETH", "POLYGON"}
    callbacks = _callbacks(wallet_network_keyboard("ar"))
    for network in SUPPORTED_WALLET_NETWORKS:
        assert f"wallet_network_{network}" in callbacks
