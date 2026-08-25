"""Release-gate checks for the current production routing surface."""
import importlib
from pathlib import Path

POLICY_MODULES = [
    "handlers.admin_approval_policy", "handlers.admin_broadcast_policy",
    "handlers.admin_maintenance_policy", "handlers.admin_navigation_policy",
    "handlers.admin_order_list_policy", "handlers.admin_payment_confirmation_policy",
    "handlers.admin_rejection_policy", "handlers.admin_settings_policy",
    "handlers.admin_tools_policy", "handlers.admin_transfer_policy",
    "handlers.admin_user_management_policy", "handlers.admin_utility_policy",
    "handlers.customer_navigation_policy", "handlers.customer_orders_policy",
    "handlers.customer_settings_policy", "handlers.language_policy",
    "handlers.order_amount_policy", "handlers.order_confirmation_policy",
    "handlers.order_wallet_policy", "handlers.order_wallet_qr_policy",
    "handlers.payment_currency_policy", "handlers.payment_method_setup_policy",
    "handlers.receipt_document_policy", "handlers.receipt_processing_policy",
    "handlers.saved_wallets", "handlers.verification_policy",
    "handlers.verification_admin_policy", "handlers.verification_pending_policy",
    "handlers.wallet_qr_first_policy", "handlers.wallets",
]

REMOVED_MODULES = (
    "handlers.admin", "handlers.admin_settings_alias_policy", "handlers.legacy_wallet_guard",
    "handlers.verification", "handlers.verification_pending_guard", "services.order_wallet_guard",
    "database_wallet_guards", "handlers.my_orders", "handlers.receipt_transition_policy",
    "handlers.payment_methods",
)


def test_release_policy_modules_import():
    for module_name in POLICY_MODULES:
        module = importlib.import_module(module_name)
        assert hasattr(module, "router"), module_name


def test_removed_compatibility_modules_are_not_importable_from_the_repository():
    root = Path(__file__).resolve().parents[1]
    for module_name in REMOVED_MODULES:
        relative = Path(*module_name.split("."))
        assert not (root / relative).with_suffix(".py").exists()


def test_authoritative_order_services_import():
    for module_name in (
        "services.order_state_service", "services.order_completion_service",
        "services.receipt_verifier", "services.receipt_media", "services.exchange_service",
        "services.settings_service", "services.receipt_service", "database_order_constraints",
        "services.legal_policy",
    ):
        importlib.import_module(module_name)


def test_release_gate_does_not_require_retired_monolithic_order_handler():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "handlers" / "order.py").exists()
    assert not (root / "handlers" / "my_orders.py").exists()
