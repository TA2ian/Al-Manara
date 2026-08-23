from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wallet_architecture_has_single_registration_owner():
    wallets = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
    qr_first = (ROOT / "handlers/wallet_qr_first_policy.py").read_text(encoding="utf-8")
    saved = (ROOT / "handlers/saved_wallets.py").read_text(encoding="utf-8")

    assert "@router.callback_query(F.data == \"wallet_add\")" in wallets
    assert "@router.message(WalletStates.waiting_address)" in wallets
    assert "@router.message(WalletStates.waiting_qr, F.photo)" in wallets
    assert "@router.message(WalletStates.waiting_address, F.photo)" in qr_first

    # saved_wallets is an order-side selector/persistence compatibility router,
    # not a second interactive wallet-registration flow.
    assert "@router.callback_query(F.data.startswith(\"order_use_saved_\"))" in saved
    assert "@router.callback_query(OrderStates.waiting_save_address, F.data == \"save_address_yes\")" in saved


def test_order_wallet_flow_never_collects_qr_as_order_data():
    source = (ROOT / "handlers/order_wallet_policy.py").read_text(encoding="utf-8")
    assert "@router.message(OrderStates.waiting_wallet_qr, F.photo)" in source
    assert "QR is not uploaded with every order" in source or "لا يتم رفع QR مع كل طلب" in source
    assert "WalletStates.waiting_address" in source
    assert "wallet_qr_photo_id" not in source.split("@router.message(OrderStates.waiting_wallet_qr, F.photo)", 1)[1]


def test_legacy_wallet_qr_state_is_only_a_compatibility_guard():
    states = (ROOT / "states.py").read_text(encoding="utf-8")
    guard = (ROOT / "handlers/legacy_wallet_guard.py").read_text(encoding="utf-8")
    order_policy = (ROOT / "handlers/order_wallet_policy.py").read_text(encoding="utf-8")

    assert "waiting_wallet_qr = State()" in states
    assert "@router.callback_query(OrderStates.waiting_wallet_qr)" in guard
    assert "@router.message(OrderStates.waiting_wallet_qr)" in guard
    assert "retired per-order QR" in guard or "old" in guard
    assert "@router.message(OrderStates.waiting_wallet_qr, F.photo)" in order_policy


def test_dispatcher_order_keeps_qr_first_before_wallet_registry():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert source.index("dp.include_router(wallet_qr_first_policy.router)") < source.index("dp.include_router(wallets.router)")
    assert source.index("dp.include_router(legacy_wallet_guard.router)") < source.index("dp.include_router(wallet_qr_first_policy.router)")
    assert source.index("dp.include_router(saved_wallets.router)") < source.index("dp.include_router(order_wallet_policy.router)")
