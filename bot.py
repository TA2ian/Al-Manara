"""Bot instance creation."""
from aiogram import Dispatcher


def create_dispatcher() -> Dispatcher:
    """Create dispatcher with authoritative handlers in precedence order."""
    from handlers import (
        start,
        saved_wallets,
        order_wallet_policy,
        order_wallet_qr_policy,
        payment_currency_policy,
        legacy_wallet_guard,
        wallets,
        order_amount_policy,
        order_confirmation_policy,
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
        verification_pending_guard,
        admin_rate_policy,
        admin_navigation_policy,
        admin_approval_policy,
        admin_rejection_policy,
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
        admin_tools_policy,
        admin_search_policy,
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

    # Dedicated input routers must precede broad legacy catch-alls.
    dp.include_router(admin_note_policy.router)
    dp.include_router(admin_tools_policy.router)
    dp.include_router(admin_search_policy.router)

    # The main order-menu command must have precedence over any stale
    # wallet-registration FSM state. Otherwise a user who previously entered
    # a wallet label/address and then presses "Create buy order" can have that
    # menu command consumed as wallet input instead of returning to the order
    # flow / active-order guidance.
    dp.include_router(order_amount_policy.router)

    dp.include_router(saved_wallets.router)
    dp.include_router(order_wallet_policy.router)
    dp.include_router(order_wallet_qr_policy.router)
    dp.include_router(payment_currency_policy.router)
    dp.include_router(legacy_wallet_guard.router)
    dp.include_router(wallets.router)
    dp.include_router(order_confirmation_policy.router)
    dp.include_router(active_order_policy.router)
    dp.include_router(profile.router)
    dp.include_router(receipt_processing_policy.router)
    dp.include_router(receipt_document_policy.router)
    dp.include_router(receipt_transition_policy.router)
    dp.include_router(customer_orders_policy.router)
    dp.include_router(my_orders.router)
    dp.include_router(feedback.router)
    dp.include_router(admin_entry.router)
    dp.include_router(admin_broadcast_policy.router)
    dp.include_router(verification_admin_policy.router)
    dp.include_router(admin_rate_policy.router)
    dp.include_router(admin_navigation_policy.router)
    dp.include_router(admin_approval_policy.router)
    dp.include_router(admin_rejection_policy.router)
    dp.include_router(admin_payment_confirmation_policy.router)
    dp.include_router(admin_transfer_policy.router)
    dp.include_router(payment_methods.router)
    # This guard must precede the legacy verification router. It blocks a
    # second request when the database status is already pending, while
    # delegating rejected/not-verified submissions to the existing flow.
    dp.include_router(verification_pending_guard.router)
    dp.include_router(verification.router)
    dp.include_router(customer_navigation_policy.router)
    dp.include_router(customer_settings_policy.router)
    dp.include_router(menu.router)

    return dp
