"""Bot instance creation."""
from aiogram import Dispatcher


def create_dispatcher() -> Dispatcher:
    """Create dispatcher with all handlers."""
    from handlers import (
        start,
        saved_wallets,
        order_wallet_policy,
        payment_currency_policy,
        order_summary_policy,
        legacy_wallet_guard,
        wallets,
        order,
        profile,
        my_orders,
        feedback,
        admin_entry,
        admin_broadcast_policy,
        verification_admin_policy,
        admin_navigation_policy,
        admin_approval_policy,
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
    # Payment currency selection must acknowledge callbacks and handle
    # calculation failures before the legacy order router can leave Telegram
    # buttons spinning.
    dp.include_router(payment_currency_policy.router)
    # Authoritative customer-facing summary must precede the legacy currency
    # handler so the final quote is clear and unambiguous.
    dp.include_router(order_summary_policy.router)
    dp.include_router(legacy_wallet_guard.router)
    dp.include_router(wallets.router)
    dp.include_router(order.router)
    dp.include_router(profile.router)
    dp.include_router(my_orders.router)
    dp.include_router(feedback.router)
    dp.include_router(admin_entry.router)
    # Broadcast, verification, navigation, and approval policies must run
    # before legacy admin handlers.
    dp.include_router(admin_broadcast_policy.router)
    dp.include_router(verification_admin_policy.router)
    dp.include_router(admin_navigation_policy.router)
    dp.include_router(admin_approval_policy.router)
    dp.include_router(payment_methods.router)
    dp.include_router(admin.router)
    dp.include_router(verification.router)
    dp.include_router(menu.router)

    return dp
