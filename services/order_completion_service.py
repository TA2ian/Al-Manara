"""Service for finalizing an approved USDT order."""
import asyncio
import html
import logging

from aiogram import Bot

from config import Config
from database import get_pool
from services.formatters import usdt
from services.order_fulfillment_claim import release_claim_after_completion
from services.order_state_service import InvalidOrderTransition, transition_order
from services.time_service import utc_now_naive
from services.transaction_verifier import verify_transaction

logger = logging.getLogger(__name__)


async def complete_order(msg, state, txid: str, screenshot_id: str, order_id: int, admin_id: int):
    """Finalize an approved USDT order only after independent on-chain verification."""
    txid = (txid or "").strip()
    if not txid:
        await msg.answer("❌ TXID غير صالح.")
        await state.clear()
        return False

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name, u.username, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )
        claim = await conn.fetchrow(
            "SELECT admin_id FROM order_fulfillment_claims WHERE order_id = $1",
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
    if not claim or int(claim["admin_id"]) != int(admin_id):
        await msg.answer("⚠️ لا توجد جلسة تنفيذ صالحة مرتبطة بهذا الطلب والمسؤول الحالي.")
        await state.clear()
        return False

    verification = await verify_transaction(
        order["network"],
        txid,
        order["wallet_address"],
        order["amount_usdt"],
    )
    if not verification.verified:
        logger.warning(
            "Rejected unverified fulfillment transaction order_id=%s network=%s txid=%s reason=%s",
            order_id,
            order["network"],
            txid,
            verification.reason,
        )
        await msg.answer(
            "❌ لم يتم اعتماد TXID.\n\n"
            f"السبب: {verification.reason}\n\n"
            "لن يتم إكمال الطلب حتى يتم التحقق من المعاملة على الشبكة."
        )
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                "SELECT o.*, u.telegram_id, u.full_name, u.username, u.language "
                "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1 FOR UPDATE",
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

            claim = await conn.fetchrow(
                "SELECT admin_id FROM order_fulfillment_claims WHERE order_id = $1 FOR UPDATE",
                order_id,
            )
            if not claim or int(claim["admin_id"]) != int(admin_id):
                await msg.answer("⚠️ انتهت جلسة التنفيذ أو أصبحت مرتبطة بمسؤول آخر. لم يتم إكمال الطلب.")
                await state.clear()
                return False

            if (order["network"] or "").upper() != verification.network:
                await msg.answer("⚠️ تغيرت شبكة الطلب أثناء التحقق. لم يتم إكماله.")
                await state.clear()
                return False
            if (order["wallet_address"] or "").strip() != verification.recipient.strip():
                await msg.answer("⚠️ تغير عنوان محفظة الطلب أثناء التحقق. لم يتم إكماله.")
                await state.clear()
                return False
            if usdt(order["amount_usdt"]) != usdt(verification.expected_amount):
                await msg.answer("⚠️ تغير مبلغ الطلب أثناء التحقق. لم يتم إكماله.")
                await state.clear()
                return False

            try:
                await transition_order(
                    conn,
                    order_id,
                    "completed",
                    admin_id=admin_id,
                    updates={
                        "txid": txid,
                        "completed_at": utc_now_naive(),
                        "receipt_photo_id": None,
                    },
                )
            except InvalidOrderTransition:
                await msg.answer("⚠️ تم إكمال هذا الطلب مسبقاً أو تغيرت حالته.")
                await state.clear()
                return False

            await release_claim_after_completion(conn, order_id, admin_id)
            order = await conn.fetchrow(
                "SELECT o.*, u.telegram_id, u.full_name, u.username, u.language "
                "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
                order_id,
            )

    bot = Bot(token=Config.BOT_TOKEN)
    try:
        comp_lang = order["language"] or "ar"
        network_name = order["network"] or "TRC20"
        amount_text = usdt(order["amount_usdt"])

        if comp_lang == "ar":
            completion_text = (
                "✅ <b>تم إتمام طلبك بنجاح!</b>\n\n"
                f"📦 الطلب: #{order['order_number']}\n"
                f"💰 المبلغ: {amount_text} USDT إلى {network_name}\n"
                f"🔗 TXID: <code>{html.escape(txid)}</code>\n\n"
                "تم التحقق من المعاملة على الشبكة."
            )
        else:
            completion_text = (
                "✅ <b>Your order has been completed!</b>\n\n"
                f"📦 Order: #{order['order_number']}\n"
                f"💰 Amount: {amount_text} USDT on {network_name}\n"
                f"🔗 TXID: <code>{html.escape(txid)}</code>\n\n"
                "The transaction was verified on-chain."
            )
        completion_text += f"\n<a href='{verification.explorer_url}'>🔍 {'عرض على المستكشف' if comp_lang == 'ar' else 'View on explorer'}</a>"

        from keyboards.reply import compact_reply_keyboard
        try:
            if screenshot_id:
                await bot.send_photo(
                    order["telegram_id"],
                    screenshot_id,
                    caption=completion_text,
                    parse_mode="HTML",
                    reply_markup=compact_reply_keyboard(comp_lang),
                )
            else:
                await bot.send_message(
                    order["telegram_id"],
                    completion_text,
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
            f"💰 {amount_text} USDT\n"
            f"🌐 {html.escape(network_name)}\n"
            f"🔗 TXID: <code>{html.escape(txid)}</code>\n"
            "🔐 تم التحقق on-chain"
        )

        await asyncio.gather(*[
            bot.send_message(admin_id, admin_done, parse_mode="HTML")
            for admin_id in Config.ADMIN_IDS
        ], return_exceptions=True)

        try:
            await msg.answer(
                f"✅ تم إكمال الطلب #{order['order_number']} بنجاح!"
                if comp_lang == "ar" else
                f"✅ Order #{order['order_number']} completed successfully!"
            )
        except Exception:
            logger.exception("Failed to acknowledge completion to admin for order %s", order_id)

        try:
            from keyboards.inline import rating_keyboard
            await bot.send_message(
                order["telegram_id"],
                "⭐ يرجى تقييم تجربتك:" if comp_lang == "ar" else "⭐ Please rate your experience:",
                reply_markup=rating_keyboard(order_id),
            )
            await bot.send_message(order["telegram_id"], "👇", reply_markup=compact_reply_keyboard(comp_lang))
        except Exception:
            logger.exception("Failed to send rating prompt for order %s", order_id)

        return True
    finally:
        await bot.session.close()
        await state.clear()
