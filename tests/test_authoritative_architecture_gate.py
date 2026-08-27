from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "handlers"
RUNTIME_ROOTS = (ROOT / "bot.py", ROOT / "database.py", ROOT / "database_order_constraints.py", ROOT / "services", ROOT / "handlers")


def test_retired_compatibility_modules_are_absent():
    for relative_path in (
        "handlers/menu.py", "handlers/admin.py", "handlers/admin_settings_alias_policy.py", "handlers/legacy_wallet_guard.py",
        "handlers/wallet_qr_first_policy.py", "handlers/order_wallet_qr_policy.py", "handlers/verification.py", "handlers/verification_pending_guard.py",
        "handlers/payment_methods.py", "handlers/payment_method_legacy_compat.py", "handlers/my_orders.py", "handlers/order.py",
        "services/order_wallet_guard.py", "database_wallet_guards.py",
    ):
        assert not (ROOT / relative_path).exists()


def test_retired_runtime_references_are_absent():
    forbidden_tokens = ("database_wallet_guards", "install_order_wallet_guard", "services.order_wallet_guard", "handlers.legacy_wallet_guard", "wallet_qr_first_policy", "order_wallet_qr_policy", "verification_pending_guard", "payment_method_legacy_compat")
    files = []
    for root in RUNTIME_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.exists():
            files.extend(path for path in root.rglob("*.py") if path.is_file())
    for path in files:
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"retired runtime reference {token!r} found in {path}"


def test_no_runtime_import_references_deleted_handler_modules():
    deleted_modules = {"handlers.menu", "handlers.admin", "handlers.admin_settings_alias_policy", "handlers.legacy_wallet_guard", "handlers.wallet_qr_first_policy", "handlers.order_wallet_qr_policy", "handlers.verification", "handlers.verification_pending_guard", "handlers.payment_methods", "handlers.payment_method_legacy_compat", "handlers.my_orders", "handlers.order"}
    for path in HANDLERS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in deleted_modules:
                raise AssertionError(f"retired module import {node.module!r} found in {path}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in deleted_modules:
                        raise AssertionError(f"retired module import {alias.name!r} found in {path}")


def test_wallet_back_uses_canonical_customer_menu():
    source = (HANDLERS / "wallets.py").read_text(encoding="utf-8")
    assert "handlers.menu" not in source
    assert "main_menu_inline" in source
    assert "compact_reply_keyboard" in source
    assert "locale_service.get(\"main_menu\"" in source


def test_dispatcher_imports_only_existing_handler_modules():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "handlers":
            imported.update(alias.name for alias in node.names)
    for module_name in imported:
        assert (HANDLERS / f"{module_name}.py").exists(), module_name


def test_canonical_database_constraints_are_runtime_owned():
    database = (ROOT / "database.py").read_text(encoding="utf-8")
    constraints = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "database_wallet_guards" not in database
    assert "from database_order_constraints import install_order_constraints" in database
    assert "await install_order_constraints(conn)" in database
    assert "verified order wallet must have a stored QR" in constraints
    assert "order wallet QR does not match the verified saved wallet" in constraints


def test_order_wallet_state_is_canonical():
    states = (ROOT / "states.py").read_text(encoding="utf-8")
    order_wallet = (HANDLERS / "order_wallet_policy.py").read_text(encoding="utf-8")
    wallets = (HANDLERS / "wallets.py").read_text(encoding="utf-8")
    assert "waiting_wallet_qr" not in states
    assert "waiting_wallet_qr" not in order_wallet
    assert "WalletStates.waiting_network" in order_wallet
    assert "WalletStates.waiting_address" in wallets
    assert "verification_status = 'verified'" in order_wallet
    assert "qr_photo_id IS NOT NULL" in order_wallet
    assert "waiting_fee_fixed" not in states


def test_customer_navigation_has_one_runtime_owner():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    navigation = (ROOT / "handlers/customer_navigation_policy.py").read_text(encoding="utf-8")
    legal_navigation = (ROOT / "handlers/legal_navigation_policy.py").read_text(encoding="utf-8")
    assert "dp.include_router(customer_navigation_policy.router)" in bot
    assert "dp.include_router(legal_navigation_policy.router)" in bot
    for callback in ("menu_help", "quick_contact", "quick_saved_addresses", "view_addr_", "del_addr_", "quick_reorder"):
        assert callback in navigation
    assert '@router.callback_query(F.data == "menu_disclaimer")' not in navigation
    assert '@router.callback_query(F.data == "menu_disclaimer")' in legal_navigation


def test_admin_graph_has_one_runtime_owner_per_policy():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "dp.include_router(admin.router)" not in bot
    assert "admin," not in bot
    for router_name in ("admin_order_list_policy", "admin_user_management_policy", "admin_utility_policy", "admin_maintenance_policy", "admin_settings_policy"):
        assert f"dp.include_router({router_name}.router)" in bot


def test_language_policy_is_active():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "dp.include_router(language_policy.router)" in bot
