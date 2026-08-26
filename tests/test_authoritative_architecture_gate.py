from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "handlers"
RUNTIME_ROOTS = (ROOT / "bot.py", ROOT / "database.py", ROOT / "database_order_constraints.py", ROOT / "services", ROOT / "handlers")


def test_retired_compatibility_modules_are_absent():
    for relative_path in (
        "handlers/menu.py",
        "handlers/admin.py",
        "handlers/admin_settings_alias_policy.py",
        "handlers/legacy_wallet_guard.py",
        "services/order_wallet_guard.py",
        "database_wallet_guards.py",
    ):
        assert not (ROOT / relative_path).exists()


def test_retired_runtime_references_are_absent():
    forbidden_tokens = (
        "database_wallet_guards",
        "install_order_wallet_guard",
        "services.order_wallet_guard",
        "handlers.legacy_wallet_guard",
    )
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
    assert "waiting_wallet_qr" not in states
    assert "waiting_wallet_qr" not in order_wallet
    assert "WalletStates.waiting_address" in order_wallet
    assert "verification_status = 'verified'" in order_wallet
    assert "qr_photo_id IS NOT NULL" in order_wallet


def test_customer_navigation_has_one_runtime_owner():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    navigation = (HANDLERS / "customer_navigation_policy.py").read_text(encoding="utf-8")
    legal_navigation = (HANDLERS / "legal_navigation_policy.py").read_text(encoding="utf-8")
    assert "dp.include_router(customer_navigation_policy.router)" in bot
    assert "dp.include_router(legal_navigation_policy.router)" in bot
    for callback in (
        "menu_help",
        "quick_contact",
        "quick_saved_addresses",
        "view_addr_",
        "del_addr_",
        "quick_reorder",
    ):
        assert callback in navigation
    assert '@router.callback_query(F.data == "menu_disclaimer")' not in navigation
    assert '@router.callback_query(F.data == "menu_disclaimer")' in legal_navigation


def test_admin_graph_has_one_runtime_owner_per_policy():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "dp.include_router(admin.router)" not in bot
    assert "admin," not in bot
    for router_name in (
        "admin_order_list_policy",
        "admin_user_management_policy",
        "admin_utility_policy",
        "admin_maintenance_policy",
        "admin_settings_policy",
    ):
        assert f"dp.include_router({router_name}.router)" in bot


def test_language_policy_is_active():
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "dp.include_router(language_policy.router)" in bot
