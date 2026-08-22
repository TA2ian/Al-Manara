"""Release-gate checks for the current production routing surface.

These checks intentionally stay lightweight: they validate that the major
policy modules remain importable and that the compatibility/legacy guards are
present. The detailed behavioural suites cover state transitions separately.
"""

import importlib


POLICY_MODULES = [
    "handlers.admin",
    "handlers.admin_approval_policy",
    "handlers.admin_broadcast_policy",
    "handlers.admin_maintenance_policy",
    "handlers.admin_navigation_policy",
    "handlers.admin_order_list_policy",
    "handlers.admin_payment_confirmation_policy",
    "handlers.admin_rejection_policy",
    "handlers.admin_settings_policy",
    "handlers.admin_tools_policy",
    "handlers.admin_transfer_policy",
    "handlers.admin_user_management_policy",
    "handlers.admin_utility_policy",
    "handlers.customer_navigation_policy",
    "handlers.customer_orders_policy",
    "handlers.order_amount_policy",
    "handlers.order_confirmation_policy",
    "handlers.order_wallet_policy",
    "handlers.order_wallet_qr_policy",
    "handlers.payment_currency_policy",
    "handlers.payment_methods",
    "handlers.receipt_document_policy",
    "handlers.receipt_processing_policy",
    "handlers.receipt_transition_policy",
    "handlers.saved_wallets",
    "handlers.verification",
    "handlers.verification_admin_policy",
    "handlers.wallets",
]


def test_release_policy_modules_import():
    for module_name in POLICY_MODULES:
        module = importlib.import_module(module_name)
        assert hasattr(module, "router"), module_name


def test_legacy_wallet_guard_is_available():
    module = importlib.import_module("handlers.legacy_wallet_guard")
    assert hasattr(module, "router")


def test_authoritative_order_services_import():
    for module_name in (
        "services.order_state_service",
        "services.order_wallet_guard",
        "services.order_completion_service",
        "services.receipt_verifier",
        "services.exchange_service",
        "services.settings_service",
    ):
        importlib.import_module(module_name)
