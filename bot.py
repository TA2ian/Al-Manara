"""Bot instance creation."""
from aiogram import Dispatcher


def create_dispatcher() -> Dispatcher:
    """Create dispatcher with all handlers."""
    from handlers import (
        start,
        saved_wallets,
        order,
        profile,
        my_orders,
        feedback,
        admin,
        verification,
        menu,
    )
    from middleware.rate_limit import RateLimitMiddleware
    from middleware.maintenance import MaintenanceMiddleware

    dp = Dispatcher()

    # Register middlewares
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())

    # Register routers. Saved-wallet callbacks must run before the legacy order
    # handlers so a stored wallet QR is reused without another upload prompt.
    dp.include_router(start.router)
    dp.include_router(saved_wallets.router)
    dp.include_router(order.router)
    dp.include_router(profile.router)
    dp.include_router(my_orders.router)
    dp.include_router(feedback.router)
    dp.include_router(admin.router)
    dp.include_router(verification.router)
    dp.include_router(menu.router)

    return dp
