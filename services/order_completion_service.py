"""Service for finalizing an approved USDT order."""
import asyncio
import html
import logging

from aiogram import Bot

from config import Config
from database import get_pool
from services.order_state_service import InvalidOrderTransition, transition_order

logger = logging.getLogger(__name__)


async def complete_order(msg, state, txid: str, screenshot_id: str, order_id: int):
    """Finalize an order, notify the customer/admins, and request a rating."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name, u.username, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )
        if not order:
            await msg.answer("❌ الطلب غير موجود.")
            await state.clear()
            return False
        if order["status"] != "payment_confirmed":
            await msg.answer("⚠️ لا يمكن إكمال هذا الطلب من حالته الحالية.")
            await state.clear()
            return False

        try:
            order = await transition_order(
                conn,
                order_id,
                "completed",
                updates={
                    "txid": txid,
                    "completed_at": __import__("datetime").datetime.now(),
                    "wallet_qr_photo_id": None,
                    "receipt_photo_id": None,
                },
            )
        except InvalidOrderTransition:
            await msg.answer("⚠️ تم إكمال هذا الطلب مسبقاً أو تغيرت حالته.")
            await state.clear()
            return False

        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name, u.username, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )

    bot = Bot(token=Config.BOT_TOKEN)
    comp_lang = order["language"] or "ar"
    network_name = order["network"] or "TRC20"

    if comp_lang == "ar":
        completion_text = (
            f"✅ <b>تم إتمام طلبك بنجاح!</b>\n\n"
            f"📦 الطلب: #{order['order_number']}\n"
            f"💰 المبلغ: {order['amount_usdt']} USDT إلى {network_name}\n"
            f"🔗 TXID: <code>{html.escape(txid)}</code>\n\n"
            "يمكنك التحقق من المعاملة عبر مستكشف الشبكة."
        )
    else:
        completion_text = (
            f"✅ <b>Your order has been completed!</b>\n\n"
            f"📦 Order: #{order['order_number']}\n"
            f"💰 Amount: {order['amount_usdt']} USDT on {network_name}\n"
            f"🔗 TXID: <code>{html.escape(txid)}</code>\n\n"
            "You can verify the transaction on the network explorer."
        )

    if network_name == "BEP20":
        explorer_url = f"https://bscscan.com/tx/{txid}"
    else:
        explorer_url = f"https://tronscan.org/#/transaction/{txid}"
    completion_text += f"\n<a href='{explorer_url}'>🔍 {'عرض على المستكشف' if comp_lang == 'ar' else 'View on explorer'}</a>"

    from keyboards.reply import compact_reply_keyboard
    try:
        if screenshot_id:
            await bot.send_photo(
                order["telegram_id"], screenshot_id,
                caption=completion_text,
                parse_mode="HTML",
                reply_markup=compact_reply_keyboard(comp_lang),
            )
        else:
            await bot.send_message(
                order["telegram_id"], completion_text,
                parse_mode="HTML",
                reply_markup=compact_reply_keyboard(comp_lang),
            )
    except Exception:
        logger.exception("Failed to notify customer for completed order %s", order_id)

    admin_done = (
        f"✅ <b>{'تم إكمال الطلب' if comp_lang == 'ar' else 'Order completed'}</b>\n\n"
        f"👤 {html.escape(order['full_name'] or 'N/A')}\n"
        f"🆔 <code>{order['telegram_id']}</code>\n"
        f"📦 {'الطلب' if comp_lang == 'ar' else 'Order'}: #{order['order_number']}\n"
        f"💰 {order['amount_usdt']} USDT\n"
        f"🌐 {html.escape(network_name)}\n"
        f"🔗 TXID: <code>{html.escape(txid)}</code>"
    )

    await asyncio.gather(*[
        bot.send_message(admin_id, admin_done, parse_mode="HTML")
        for admin_id in Config.ADMIN_IDS
    ], return_exceptions=True)

    await msg.answer(
        f"✅ تم إكمال الطلب #{order['order_number']} بنجاح!"
        if comp_lang == "ar" else
        f"✅ Order #{order['order_number']} completed successfully!"
    )

    try:
        from keyboards.inline import rating_keyboard
        await bot.send_message(
            order["telegram_id"],
            "⭐ يرجى تقييم تجربتك:" if comp_lang == "ar" else "⭐ Please rate your experience:",
            reply_markup=rating_keyboard(order_id),
        )
        await bot.send_message(
            order["telegram_id"],
            "👇",
            reply_markup=compact_reply_keyboard(comp_lang),
        )
    except Exception:
        logger.exception("Failed to send rating prompt for order %s", order_id)

    await state.clear()
    return True
