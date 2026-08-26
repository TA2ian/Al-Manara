"""Release-gate checks for the current production routing surface."""
import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

POLICY_MODULES = [
    "handlers.start", "handlers.saved_wallets", "handlers.order_wallet_policy",
    "handlers.order_wallet_qr_policy", "handlers.payment_currency_policy",
    "handlers.wallet_qr_first_policy", "handlers.wallets", "handlers.order_amount_policy",
    "handlers.order_confirmation_policy", "handlers.profile", "handlers.active_order_policy",
    "handlers.receipt_processing_policy", "handlers.receipt_document_policy",
    "handlers.customer_orders_policy", "handlers.feedback", "handlers.admin_entry",
    "handlers.admin_reply_shortcut", "handlers.admin_broadcast_policy",
    "handlers.verification_admin_policy", "handlers.verification_pending_policy",
    "handlers.verification_policy", "handlers.verification_keyboard_cleanup",
    "handlers.admin_rate_policy", "handlers.admin_navigation_policy",
    "handlers.admin_approval_policy", "handlers.admin_rejection_policy",
    "handlers.admin_payment_confirmation_policy", "handlers.admin_transfer_policy",
    "handlers.admin_note_policy", "handlers.admin_order_list_policy",
    "handlers.admin_user_management_policy", "handlers.admin_utility_policy",
    "handlers.admin_maintenance_policy", "handlers.admin_settings_policy",
    "handlers.payment_method_setup_policy", "handlers.payment_method_callback_policy",
    "handlers.language_policy", "handlers.customer_navigation_policy",
    "handlers.customer_settings_policy", "handlers.admin_tools_policy",
    "handlers.admin_search_policy", "handlers.legal_navigation_policy",
]

REMOVED_MODULES = (
    "handlers.admin", "handlers.admin_settings_alias_policy", "handlers.legacy_wallet_guard",
    "handlers.verification", "handlers.verification_pending_guard", "services.order_wallet_guard",
    "database_wallet_guards", "handlers.my_orders", "handlers.receipt_transition_policy",
    "handlers.payment_methods", "handlers.payment_method_legacy_compat",
)


def _registered_router_modules():
    """Return router module names actually registered by bot.create_dispatcher()."""
    tree = ast.parse((ROOT / "bot.py").read_text(encoding="utf-8"))
    registered = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "include_router":
            continue
        if len(node.args) != 1:
            continue
        router = node.args[0]
        if not isinstance(router, ast.Attribute) or router.attr != "router":
            continue
        if isinstance(router.value, ast.Name):
            registered.append(router.value.id)
    return tuple(registered)


def test_release_policy_modules_import():
    for module_name in POLICY_MODULES:
        module = importlib.import_module(module_name)
        assert hasattr(module, "router"), module_name


def test_every_registered_router_is_covered_by_release_gate():
    registered = set(_registered_router_modules())
    covered = {module.rsplit(".", 1)[-1] for module in POLICY_MODULES}
    missing = sorted(registered - covered)
    assert not missing, "Production routers missing from release gate: " + repr(missing)


def test_release_gate_has_no_stale_router_entries():
    registered = set(_registered_router_modules())
    covered = {module.rsplit(".", 1)[-1] for module in POLICY_MODULES}
    stale = sorted(covered - registered)
    assert not stale, "Release gate contains unregistered routers: " + repr(stale)


def test_removed_compatibility_modules_are_not_importable_from_the_repository():
    for module_name in REMOVED_MODULES:
        relative = Path(*module_name.split("."))
        assert not (ROOT / relative).with_suffix(".py").exists()


def test_authoritative_services_import():
    for module_name in (
        "services.order_state_service", "services.order_completion_service",
        "services.receipt_verifier", "services.receipt_media", "services.exchange_service",
        "services.settings_service", "services.receipt_service", "services.maintenance_service",
        "services.admin_message_service", "services.order_invoice_service",
        "database_order_constraints", "services.legal_policy",
    ):
        importlib.import_module(module_name)


def test_release_gate_does_not_require_retired_monolithic_order_handler():
    assert not (ROOT / "handlers" / "order.py").exists()
    assert not (ROOT / "handlers" / "my_orders.py").exists()


def test_historical_payment_ingress_is_explicit_and_narrow():
    source = (ROOT / "handlers" / "payment_method_callback_policy.py").read_text(encoding="utf-8")
    assert "HISTORICAL_CODE_ALIASES" in source
    assert "HISTORICAL_CALLBACK_PATTERN" in source
    assert "CANONICAL_CODE_PATTERN" not in source
    assert "[^\\s]+" not in source
    assert "admin_pm_" in source
    assert "payment_method_setup_policy" in source
