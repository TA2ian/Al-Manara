from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_customer_dashboard_keyboard_is_not_persistent_and_supports_admin_scope():
    source = (ROOT / "keyboards/reply.py").read_text(encoding="utf-8")
    assert "is_persistent=False" in source
    assert "one_time_keyboard=True" in source
    assert "def customer_dashboard_keyboard" in source
    assert "def admin_dashboard_keyboard" in source
    assert "def remove_dashboard_keyboard" in source


def test_admin_shortcut_isolated_and_authorized():
    source = (ROOT / "handlers/admin_reply_shortcut.py").read_text(encoding="utf-8")
    assert '"👑 لوحة الأدمن"' in source
    assert '"👑 Admin Dashboard"' in source
    assert "message.from_user.id not in Config.ADMIN_IDS" in source
    assert "_send_admin_menu(message)" in source


def test_admin_shortcut_router_is_registered_before_generic_admin_routes():
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    shortcut = source.index("dp.include_router(admin_reply_shortcut.router)")
    admin_entry = source.index("dp.include_router(admin_entry.router)")
    assert shortcut < admin_entry


def test_order_start_explicitly_removes_dashboard_keyboard():
    source = (ROOT / "handlers/order_amount_policy.py").read_text(encoding="utf-8")
    assert "from keyboards.reply import remove_dashboard_keyboard" in source
    assert "reply_markup=remove_dashboard_keyboard()" in source
    assert "await state.set_state(OrderStates.waiting_amount)" in source


def test_phone_verification_uses_the_canonical_verification_router_only():
    bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
    policy_source = (ROOT / "handlers/verification_policy.py").read_text(encoding="utf-8")
    assert bot_source.count("dp.include_router(verification_policy.router)") == 1
    assert "verification_keyboard_cleanup" not in bot_source
    assert "@router.message(VerificationStates.waiting_phone, F.contact)" in policy_source
