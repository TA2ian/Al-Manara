"""Release-gate checks for the current production routing surface."""
import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

POLICY_MODULES = [
    "handlers.start", "handlers.saved_wallets", "handlers.order_wallet_policy",
    "handlers.payment_currency_policy", "handlers.wallets", "handlers.order_amount_policy",
    "handlers.order_confirmation_policy", "handlers.profile", "handlers.active_order_policy",
    "handlers.receipt_processing_policy", "handlers.receipt_document_policy",
    "handlers.customer_orders_policy", "handlers.feedback", "handlers.admin_entry",
    "handlers.admin_reply_shortcut", "handlers.admin_broadcast_policy",
    "handlers.verification_admin_policy", "handlers.verification_pending_policy",
    "handlers.verification_policy", "handlers.admin_rate_policy",
    "handlers.admin_navigation_policy", "handlers.admin_approval_policy",
    "handlers.admin_rejection_policy", "handlers.admin_payment_confirmation_policy",
    "handlers.admin_transfer_policy", "handlers.admin_note_policy",
    "handlers.admin_order_list_policy", "handlers.admin_user_management_policy",
    "handlers.admin_utility_policy", "handlers.admin_maintenance_policy",
    "handlers.admin_settings_policy", "handlers.payment_method_setup_policy",
    "handlers.language_policy", "handlers.customer_navigation_policy",
    "handlers.customer_settings_policy", "handlers.admin_tools_policy",
    "handlers.admin_search_policy", "handlers.legal_navigation_policy",
]

REMOVED_MODULES = (
    "handlers.admin", "handlers.admin_settings_alias_policy", "handlers.legacy_wallet_guard",
    "handlers.verification", "handlers.verification_pending_guard", "handlers.verification_keyboard_cleanup",
    "handlers.wallet_qr_first_policy", "services.order_wallet_guard", "database_wallet_guards",
    "handlers.my_orders", "handlers.receipt_transition_policy", "handlers.payment_methods",
    "handlers.payment_method_legacy_compat",
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


def test_retired_order_wallet_qr_guard_is_not_registered():
    bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "order_wallet_qr_policy" not in bot_source


def test_authoritative_services_import():
    for module_name in (
        "services.order_state_service", "services.order_completion_service",
        "services.receipt_verifier", "services.receipt_media", "services.exchange_service",
        "services.settings_service", "services.receipt_service", "services.maintenance_service",
        "services.admin_message_service", "services.order_invoice_service",
        "services.time_service", "services.receipt_verification_policy",
        "database_order_constraints", "services.legal_policy",
    ):
        importlib.import_module(module_name)


def test_receipt_amount_tolerance_has_one_authoritative_owner():
    verifier = (ROOT / "services/receipt_verifier.py").read_text(encoding="utf-8")
    policy = (ROOT / "services/receipt_verification_policy.py").read_text(encoding="utf-8")
    assert "from services.receipt_verification_policy import amounts_match" in verifier
    assert "* 0.02" not in verifier
    assert "AMOUNT_TOLERANCE_PERCENT = Decimal(\"0.02\")" in policy


def test_release_gate_does_not_require_retired_monolithic_order_handler():
    assert not (ROOT / "handlers" / "order.py").exists()
    assert not (ROOT / "handlers" / "my_orders.py").exists()


def test_payment_method_runtime_is_canonical_only():
    bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
    canonical_source = (ROOT / "handlers/payment_method_setup_policy.py").read_text(encoding="utf-8")
    assert "payment_method_setup_policy" in bot_source
    assert "payment_method_callback_policy" not in bot_source
    assert "payment_method_legacy_compat" not in bot_source
    assert "CANONICAL_CODE_PATTERN" in canonical_source


def test_wallet_runtime_is_canonical_only():
    bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "wallet_qr_first_policy" not in bot_source
    assert "order_wallet_qr_policy" not in bot_source
    assert "handlers.wallets" not in bot_source
    assert "dp.include_router(wallets.router)" in bot_source


def test_verification_runtime_is_canonical_only():
    bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "verification_keyboard_cleanup" not in bot_source
    assert "verification_pending_guard" not in bot_source
    assert "verification_policy" in bot_source
    assert "verification_admin_policy" in bot_source
