"""Bot instance creation."""
from aiogram import Bot, Dispatcher

from config import Config


def create_bot() -> Bot:
    """Create bot instance."""
    return Bot(token=Config.BOT_TOKEN)


def create_dispatcher() -> Dispatcher:
    """Create dispatcher with all handlers."""
    from handlers import start, order, profile, my_orders, feedback, admin, verification, menu
    from middleware.rate_limit import RateLimitMiddleware
    from middleware.maintenance import MaintenanceMiddleware

    dp = Dispatcher()

    # Register middlewares
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(order.router)
    dp.include_router(profile.router)
    dp.include_router(my_orders.router)
    dp.include_router(feedback.router)
    dp.include_router(admin.router)
    dp.include_router(verification.router)
    dp.include_router(menu.router)

    return dp
