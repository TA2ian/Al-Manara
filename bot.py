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
        order,
        profile,
        active_order_policy,
        receipt_processing_policy,
        customer_orders_policy,
        my_orders,
        feedback,
        admin_entry,
        admin_broadcast_policy,
        verification_admin_policy,
        admin_navigation_policy,
        admin_approval_policy,
        admin_transfer_policy,
        admin,
        payment_methods,
        verification,
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
    # Wallet policy and the stale-session guard must precede the wallet
    # registry and legacy order handlers.
    dp.include_router(order_wallet_policy.router)
    # Payment currency selection is the authoritative customer quote handler
    # and must run before the legacy order router.
    dp.include_router(payment_currency_policy.router)
    dp.include_router(legacy_wallet_guard.router)
    dp.include_router(wallets.router)
    # If a verified customer already has an active order, guide them to Orders
    # instead of starting another order flow.
    dp.include_router(active_order_policy.router)
    dp.include_router(order.router)
    dp.include_router(profile.router)
    # Receipt progress must precede my_orders so the temporary processing
    # message appears while the existing OCR/verification handler works.
    dp.include_router(receipt_processing_policy.router)
    # Precise customer-facing statuses must precede the legacy order-history
    # handlers, including pagination callbacks.
    dp.include_router(customer_orders_policy.router)
    dp.include_router(my_orders.router)
    dp.include_router(feedback.router)
    dp.include_router(admin_entry.router)
    # Broadcast, verification, navigation, and approval policies must run
    # before legacy admin handlers.
    dp.include_router(admin_broadcast_policy.router)
    dp.include_router(verification_admin_policy.router)
    dp.include_router(admin_navigation_policy.router)
    dp.include_router(admin_approval_policy.router)
    # Admin transfer-proof input must precede the legacy TXID handlers so a
    # screenshot can safely be submitted before or together with its TXID.
    dp.include_router(admin_transfer_policy.router)
    dp.include_router(payment_methods.router)
    dp.include_router(admin.router)
    dp.include_router(verification.router)
    dp.include_router(menu.router)

    return dp
