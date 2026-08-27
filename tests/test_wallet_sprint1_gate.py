from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wallet_architecture_has_single_registration_owner():
    wallets = (ROOT / "handlers/wallets.py").read_text(encoding="utf-8")
    saved = (ROOT / "handlers/saved_wallets.py").read_text(encoding="utf-8")

    assert "@router.callback_query(F.data == \"wallet_add\")" in wallets
    assert "@router.callback_query(WalletStates.waiting_network, F.data.startswith(\"wallet_network_\"))" in wallets
    assert "@router.message(WalletStates.waiting_address)" in wallets
    assert "@router.message(WalletStates.waiting_address, F.photo)" in wallets
    assert "@router.message(WalletStates.waiting_qr, F.photo)" in wallets
    assert "@router.callback_query(F.data.startswith(\"order_use_saved_\"))" in saved


def test_order_wallet_flow_uses_only_verified_saved_wallets_or_registry():
    source = (ROOT / "handlers/order_wallet_policy.py").read_text(encoding="utf-8")
    assert "WalletStates.waiting_network" in source
    assert "verification_status = 'verified'" in source
    assert "qr_photo_id IS NOT NULL" in source
    assert "waiting_wallet_qr" not in source
    assert "skip_wallet_qr" not in source
    assert "save_address_skip" not in source


def test_retired_per_order_wallet_qr_architecture_is_absent():
    states = (ROOT / "states.py").read_text(encoding="utf-8")
    bot = (ROOT / "bot.py").read_text(encoding="utf-8")

    assert "waiting_wallet_qr" not in states
    assert "legacy_wallet_guard" not in bot
    assert not (ROOT / "handlers/legacy_wallet_guard.py").exists()


def test_dispatcher_uses_one_wallet_registration_router():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    assert "wallet_qr_first_policy" not in source
    assert "order_wallet_qr_policy" not in source
    assert source.index("dp.include_router(saved_wallets.router)") < source.index("dp.include_router(order_wallet_policy.router)")
    assert source.index("dp.include_router(order_wallet_policy.router)") < source.index("dp.include_router(wallets.router)")


def test_back_to_wallet_returns_to_wallet_state_not_currency_state():
    source = (ROOT / "handlers/order_wallet_policy.py").read_text(encoding="utf-8")
    back_block = source.split("@router.callback_query(F.data == \"back_to_wallet\")", 1)[1].split("@router.callback_query", 1)[0]

    assert "await state.set_state(OrderStates.waiting_wallet)" in back_block
    assert "await state.set_state(OrderStates.waiting_currency)" not in back_block
    assert "qr_photo_id IS NOT NULL" in back_block


def test_stale_currency_callbacks_are_blocked_while_selecting_wallet():
    source = (ROOT / "handlers/order_wallet_policy.py").read_text(encoding="utf-8")
    assert '@router.callback_query(OrderStates.waiting_wallet, F.data.startswith("currency_"))' in source
    assert "Select a wallet first to continue." in source or "اختر المحفظة أولاً لمتابعة الطلب." in source
