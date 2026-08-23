"""Regression coverage for admin destructive/rejection actions and wallet UX."""
import inspect

from handlers import admin_rejection_policy, admin_user_management_policy, verification_admin_policy, wallets
from keyboards.inline import order_admin_keyboard


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


def test_order_rejection_is_exposed_for_all_rejectable_active_states():
    for status in ("pending", "waiting_payment", "receipt_received", "payment_confirmed"):
        callbacks = _callbacks(order_admin_keyboard(123, status))
        assert "admin_reject_123" in callbacks


def test_order_rejection_uses_authoritative_transition():
    source = inspect.getsource(admin_rejection_policy.reject_order)
    assert "transition_order" in source
    assert '"rejected"' in source
    assert "admin_id=callback.from_user.id" in source


def test_wallet_add_message_describes_all_supported_inputs_and_matching():
    source = inspect.getsource(wallets.wallet_add)
    assert "عنوان المحفظة" in source
    assert "صورة <b>QR</b>" in source
    assert "شارك المحفظة مباشرة" in source
    assert "العنوان مع QR" in source
    assert "يطابق العنوان مع QR" in source
    assert "BEP20" in source
    assert "TRC20" in source
    assert "لن يتم حفظ العنوان بمجرد إرساله" not in source


if __name__ == "__main__":
    import unittest
    unittest.main()
