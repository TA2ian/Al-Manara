"""Main entry point for Crypto Top-Up Bot."""
import asyncio
import logging
import sys
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import Config
from database import init_db, close_db
from bot import create_dispatcher
from keep_alive import keep_alive

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s|%(levelname)s|%(name)s|%(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Startup handler."""
    logger.info("Starting bot...")

    # Initialize database
    await init_db()

    # Set webhook if configured
    if Config.WEBHOOK_URL:
        await bot.set_webhook(
            url=Config.WEBHOOK_URL,
            secret_token=Config.SECRET_TOKEN,
            drop_pending_updates=True
        )
        logger.info(f"Webhook set: {Config.WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    """Shutdown handler."""
    logger.info("Shutting down...")

    await bot.delete_webhook()
    await close_db()


async def main():
    """Main function."""
    # Validate config
    errors = Config.validate()
    if errors:
        logger.error(f"Config errors: {errors}")
        sys.exit(1)

    # Create bot and dispatcher
    bot = Bot(token=Config.BOT_TOKEN)
    dp = create_dispatcher()

    # Register startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Create aiohttp app
    app = web.Application()

    # Webhook handler
    if Config.WEBHOOK_URL:
        webhook_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=Config.SECRET_TOKEN
        )
        webhook_handler.register(app, path=Config.WEBHOOK_PATH)

        setup_application(app, dp, bot=bot)

    # Keep alive
    keep_alive(app)

    # Run server
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host=Config.HOST, port=Config.PORT)
    await site.start()

    logger.info(f"Server started on {Config.HOST}:{Config.PORT}")

    # Keep running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
