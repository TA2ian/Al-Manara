"""Bot instance creation."""
from aiogram import Dispatcher


def create_dispatcher() -> Dispatcher:
    """Create dispatcher with all handlers."""
    from handlers import (
        start,
        saved_wallets,
        order_wallet_policy,
        wallets,
        order,
        profile,
        my_orders,
        feedback,
        admin_entry,
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
    # Wallet policy must precede both the wallet registry and legacy order
    # handlers so order-created wallet registration can resume correctly.
    dp.include_router(order_wallet_policy.router)
    dp.include_router(wallets.router)
    dp.include_router(order.router)
    dp.include_router(profile.router)
    dp.include_router(my_orders.router)
    dp.include_router(feedback.router)
    dp.include_router(admin_entry.router)
    dp.include_router(payment_methods.router)
    dp.include_router(admin.router)
    dp.include_router(verification.router)
    dp.include_router(menu.router)

    return dp
