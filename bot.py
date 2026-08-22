"""Bot instance creation."""
from aiogram import Dispatcher


def create_dispatcher() -> Dispatcher:
    """Create dispatcher with all handlers."""
    from handlers import (
        start,
        saved_wallets,
        order_wallet_policy,
        payment_currency_policy,
        legacy_wallet_guard,
        wallets,
        order_amount_policy,
        order_confirmation_policy,
        order,
        profile,
        active_order_policy,
        receipt_processing_policy,
        receipt_document_policy,
        receipt_transition_policy,
        customer_orders_policy,
        my_orders,
        feedback,
        admin_entry,
        admin_broadcast_policy,
        verification_admin_policy,
        admin_financial_dashboard_policy,
        admin_rate_policy,
        admin_navigation_policy,
        admin_approval_policy,
        admin_payment_confirmation_policy,
        admin_transfer_policy,
        admin_note_policy,
        admin,
        payment_methods,
        verification,
        language_policy,
        customer_navigation_policy,
        customer_settings_policy,
        menu,
    )
    from middleware.rate_limit import RateLimitMiddleware
    from middleware.maintenance import MaintenanceMiddleware
    from middleware.ownership import OwnershipMiddleware

    dp = Dispatcher()
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(OwnershipMiddleware())

    dp.include_router(start.router)
    dp.include_router(saved_wallets.router)
    dp.include_router(order_wallet_policy.router)
    dp.include_router(payment_currency_policy.router)
    dp.include_router(legacy_wallet_guard.router)
    dp.include_router(wallets.router)
    dp.include_router(order_amount_policy.router)
    dp.include_router(order_confirmation_policy.router)
    dp.include_router(active_order_policy.router)
    dp.include_router(order.router)
    dp.include_router(profile.router)
    dp.include_router(receipt_processing_policy.router)
    dp.include_router(receipt_document_policy.router)
    # Retry/manual-review callbacks must precede their legacy equivalents so
    # state changes go through order_state_service atomically.
    dp.include_router(receipt_transition_policy.router)
    dp.include_router(customer_orders_policy.router)
    dp.include_router(my_orders.router)
    dp.include_router(feedback.router)
    dp.include_router(admin_entry.router)
    dp.include_router(admin_broadcast_policy.router)
    dp.include_router(verification_admin_policy.router)
    dp.include_router(admin_financial_dashboard_policy.router)
    # Rate input must precede legacy/admin navigation handlers for the same FSM state.
    dp.include_router(admin_rate_policy.router)
    dp.include_router(admin_navigation_policy.router)
    dp.include_router(admin_approval_policy.router)
    # Payment confirmation must precede the legacy admin.py implementation.
    dp.include_router(admin_payment_confirmation_policy.router)
    dp.include_router(admin_transfer_policy.router)
    dp.include_router(admin_note_policy.router)
    dp.include_router(payment_methods.router)
    dp.include_router(admin.router)
    dp.include_router(language_policy.router)
    dp.include_router(verification.router)
    dp.include_router(customer_navigation_policy.router)
    # Customer settings entry must precede the legacy menu handler.
    dp.include_router(customer_settings_policy.router)
    dp.include_router(menu.router)

    return dp
