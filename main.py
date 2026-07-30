"""Main entry point for Crypto Top-Up Bot."""
import asyncio
import logging
import sys
from datetime import datetime, timedelta

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import Config
from database import init_db, close_db, get_pool
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


async def send_expiry_reminders(bot: Bot):
    """Background task: warn users 10 minutes before payment deadline."""
    while True:
        try:
            pool = await get_pool()
            if pool:
                async with pool.acquire() as conn:
                    soon_expiring = await conn.fetch(
                        "SELECT o.*, u.telegram_id, u.language FROM orders o "
                        "JOIN users u ON o.user_id = u.id "
                        "WHERE o.status = 'waiting_payment' "
                        "AND o.payment_deadline BETWEEN NOW() + INTERVAL '9 minutes' AND NOW() + INTERVAL '12 minutes'"
                    )
                    for order in soon_expiring:
                        remaining = int((order['payment_deadline'] - datetime.now()).total_seconds() / 60)
                        lang = order['language'] or 'ar'
                        msg = (
                            f"⏰ <b>تنبيه: المهلة على وشك الانتهاء!</b>\n\n"
                            f"📦 الطلب: #{order['order_number']}\n"
                            f"💰 المبلغ: {order['amount_usdt']} USDT\n"
                            f"⏱ الوقت المتبقي: <b>{remaining} دقائق</b>\n\n"
                            f"⚠️ يرجى إرسال إيصال الدفع قبل انتهاء المهلة."
                        ) if lang == 'ar' else (
                            f"⏰ <b>Warning: Payment deadline approaching!</b>\n\n"
                            f"📦 Order: #{order['order_number']}\n"
                            f"💰 Amount: {order['amount_usdt']} USDT\n"
                            f"⏱ Time remaining: <b>{remaining} minutes</b>\n\n"
                            f"⚠️ Please upload your payment receipt before the deadline."
                        )
                        try:
                            from keyboards.inline import receipt_upload_keyboard
                            await bot.send_message(
                                order['telegram_id'], msg,
                                reply_markup=receipt_upload_keyboard(order['id'], lang),
                                parse_mode='HTML'
                            )
                        except Exception as e:
                            logger.error(f"Expiry reminder failed for {order['telegram_id']}: {e}")
                    if soon_expiring:
                        logger.info(f"Sent {len(soon_expiring)} expiry reminders")
        except Exception as e:
            logger.error(f"Expiry reminder check failed: {e}")
        await asyncio.sleep(300)


async def check_expired_orders(bot: Bot):
    """Background task: auto-cancel orders past payment deadline."""
    while True:
        try:
            pool = await get_pool()
            if pool:
                async with pool.acquire() as conn:
                    expired = await conn.fetch(
                        "SELECT o.*, u.telegram_id FROM orders o "
                        "JOIN users u ON o.user_id = u.id "
                        "WHERE o.status = 'waiting_payment' "
                        "AND o.payment_deadline < NOW()"
                    )
                    for order in expired:
                        await conn.execute(
                            "UPDATE orders SET status = 'expired' WHERE id = $1",
                            order['id']
                        )
                        try:
                            await bot.send_message(
                                order['telegram_id'],
                                f"⏰ <b>انتهت مهلة الدفع</b>\n\n"
                                f"📦 الطلب: #{order['order_number']}\n"
                                f"💰 المبلغ: {order['amount_usdt']} USDT\n\n"
                                f"انتهت المدة المحددة للدفع. يمكنك إنشاء طلب جديد.",
                                parse_mode='HTML'
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify user {order['telegram_id']}: {e}")
                    if expired:
                        logger.info(f"Auto-cancelled {len(expired)} expired orders")
        except Exception as e:
            logger.error(f"Expired order check failed: {e}")
        await asyncio.sleep(60)


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

    # Start background tasks
    asyncio.create_task(check_expired_orders(bot))
    asyncio.create_task(send_expiry_reminders(bot))
    logger.info("Background expiry checker started")


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
