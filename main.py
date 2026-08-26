"""Main entry point for Al-Manara customer top-up bot."""
import asyncio
import logging
import os
import sys
from datetime import datetime

from aiohttp import web
from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import Config
from database import init_db, close_db, get_pool
from database_receipt_retry_constraints import install_receipt_retry_constraints
from bot import create_dispatcher
from keep_alive import keep_alive
from services.maintenance_service import MaintenanceMode, MaintenanceService
from services.order_state_service import transition_order, InvalidOrderTransition
from services.fulfillment_claim_service import init_fulfillment_claims
from services.formatters import usdt

os.makedirs("logs", exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(name)s|%(message)s', handlers=[logging.FileHandler('logs/bot.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
_background_tasks: set[asyncio.Task] = set()


def _track_background_task(coro, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def send_expiry_reminders(bot: Bot):
    """Warn users 10 minutes before their payment deadline."""
    while True:
        try:
            pool = await get_pool()
            if pool:
                async with pool.acquire() as conn:
                    soon_expiring = await conn.fetch("SELECT o.*, u.telegram_id, u.language FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = 'waiting_payment' AND COALESCE(o.receipt_upload_count, 0) < 3 AND o.payment_deadline BETWEEN NOW() + INTERVAL '9 minutes' AND NOW() + INTERVAL '12 minutes'")
                    for order in soon_expiring:
                        remaining = int((order['payment_deadline'] - datetime.now()).total_seconds() / 60)
                        lang = order['language'] or 'ar'
                        amount_usdt = usdt(order['amount_usdt'])
                        msg = (f"⏰ <b>تنبيه: المهلة على وشك الانتهاء!</b>\n\n📦 الطلب: #{order['order_number']}\n💰 المبلغ: {amount_usdt} USDT\n⏱ الوقت المتبقي: <b>{remaining} دقائق</b>\n\n⚠️ يرجى إرسال إيصال الدفع قبل انتهاء المهلة.") if lang == 'ar' else (f"⏰ <b>Warning: Payment deadline approaching!</b>\n\n📦 Order: #{order['order_number']}\n💰 Amount: {amount_usdt} USDT\n⏱ Time remaining: <b>{remaining} minutes</b>\n\n⚠️ Please upload your payment receipt before the deadline.")
                        try:
                            from keyboards.inline import receipt_upload_keyboard
                            await bot.send_message(order['telegram_id'], msg, reply_markup=receipt_upload_keyboard(order['id'], lang), parse_mode='HTML')
                        except Exception as exc:
                            logger.error("Expiry reminder failed for %s: %s", order['telegram_id'], exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Expiry reminder check failed: %s", exc)
        await asyncio.sleep(300)


async def check_expired_orders(bot: Bot):
    """Atomically expire orders past their payment deadline."""
    while True:
        try:
            pool = await get_pool()
            if pool:
                async with pool.acquire() as conn:
                    expired = await conn.fetch("SELECT o.*, u.telegram_id, u.language FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = 'waiting_payment' AND COALESCE(o.receipt_upload_count, 0) < 3 AND o.payment_deadline < NOW()")
                    for order in expired:
                        try:
                            await transition_order(conn, order['id'], 'expired')
                        except InvalidOrderTransition:
                            continue
                        exp_lang = order['language'] or 'ar'
                        amount_usdt = usdt(order['amount_usdt'])
                        from keyboards.reply import compact_reply_keyboard
                        exp_msg = (f"⏰ <b>انتهت مهلة الدفع</b>\n\n📦 الطلب: #{order['order_number']}\n💰 المبلغ: {amount_usdt} USDT\n\nانتهت المدة المحددة للدفع. يمكنك إنشاء طلب جديد بالضغط على <b>💰 إنشاء طلب شراء</b>.") if exp_lang == 'ar' else (f"⏰ <b>Payment deadline expired</b>\n\n📦 Order: #{order['order_number']}\n💰 Amount: {amount_usdt} USDT\n\nThe payment deadline has expired. You can create a new order by pressing <b>💰 Buy Order</b>.")
                        try:
                            await bot.send_message(order['telegram_id'], exp_msg, parse_mode='HTML', reply_markup=compact_reply_keyboard(exp_lang))
                        except Exception as exc:
                            logger.error("Failed to notify user %s: %s", order['telegram_id'], exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Expired order check failed: %s", exc)
        await asyncio.sleep(60)


async def maintenance_notification_worker(bot: Bot):
    """Deliver durable maintenance notification jobs with bounded retries."""
    while True:
        processed = 0
        try:
            processed = await MaintenanceService.process_notification_jobs(bot, batch_size=50)
            if processed:
                logger.info("Processed %s maintenance notification jobs", processed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Maintenance notification worker failed")
        await asyncio.sleep(2 if processed else 5)


async def on_startup(bot: Bot):
    logger.info("Starting bot...")
    await init_db()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await install_receipt_retry_constraints(conn)
    await init_fulfillment_claims()
    maintenance_mode = await MaintenanceService.get_mode()
    Config.set_maintenance_mode_sync(maintenance_mode in {MaintenanceMode.MAINTENANCE, MaintenanceMode.EMERGENCY})
    if maintenance_mode != MaintenanceMode.OFF:
        logger.info("Maintenance mode is ACTIVE: %s", maintenance_mode.value)

    if Config.WEBHOOK_URL:
        await bot.set_webhook(url=Config.WEBHOOK_URL, secret_token=Config.SECRET_TOKEN, drop_pending_updates=True)
        logger.info("Webhook set: %s", Config.WEBHOOK_URL)

    _track_background_task(check_expired_orders(bot), 'order-expiry-checker')
    _track_background_task(send_expiry_reminders(bot), 'expiry-reminder-worker')
    _track_background_task(maintenance_notification_worker(bot), 'maintenance-notification-worker')
    logger.info("Background workers started")


async def on_shutdown(bot: Bot):
    logger.info("Shutting down...")
    tasks = list(_background_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _background_tasks.clear()
    await bot.delete_webhook()
    await close_db()


async def main():
    errors = Config.validate()
    if errors:
        logger.error("Config errors: %s", errors)
        sys.exit(1)
    bot = Bot(token=Config.BOT_TOKEN)
    dp = create_dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    app = web.Application()
    if Config.WEBHOOK_URL:
        webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=Config.SECRET_TOKEN)
        webhook_handler.register(app, path=Config.WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
    keep_alive(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=Config.HOST, port=Config.PORT)
    await site.start()
    logger.info("Server started on %s:%s", Config.HOST, Config.PORT)
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
