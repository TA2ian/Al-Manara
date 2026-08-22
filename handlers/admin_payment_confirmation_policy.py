"""Authoritative admin payment-confirmation policy."""
import asyncio
import html
import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import order_admin_keyboard
from keyboards.reply import compact_reply_keyboard
from services.order_state_service import InvalidOrderTransition, transition_order

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.callback_query(F.data.startswith("admin_confirm_payment_"))
async def confirm_payment(callback: CallbackQuery):
    """Confirm a receipt only from receipt_received, then queue fulfillment."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.removeprefix("admin_confirm_payment_"))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            """
            SELECT o.*, u.telegram_id, u.full_name, u.username, u.language
            FROM orders o JOIN users u ON o.user_id = u.id
            WHERE o.id = $1
            """,
            order_id,
        )
        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True)
            return
        if order["status"] != "receipt_received":
            await callback.answer(f"⚠️ حالة الطلب الحالية: {order['status']}", show_alert=True)
            return
        try:
            order = await transition_order(
                conn,
                order_id,
                "payment_confirmed",
                admin_id=callback.from_user.id,
            )
        except InvalidOrderTransition:
            await callback.answer("⚠️ تم تحديث الطلب مسبقاً أو تغيرت حالته", show_alert=True)
            return
        order = await conn.fetchrow(
            """
            SELECT o.*, u.telegram_id, u.full_name, u.username, u.language
            FROM orders o JOIN users u ON o.user_id = u.id
            WHERE o.id = $1
            """,
            order_id,
        )

    lang = order["language"] or "ar"
    bot = Bot(token=Config.BOT_TOKEN)
    try:
        await bot.send_message(
            order["telegram_id"],
            f"✅ <b>تم تأكيد الدفع!</b>\n\n"
            f"📦 الطلب: #{order['order_number']}\n"
            f"💰 المبلغ: {order['amount_usdt']} USDT\n"
            "⏳ تم تحويل الطلب إلى مرحلة إرسال USDT. سيقوم المشرف بإتمام التحويل إلى محفظتك."
            if lang == "ar" else
            f"✅ <b>Payment confirmed!</b>\n\n"
            f"📦 Order: #{order['order_number']}\n"
            f"💰 Amount: {order['amount_usdt']} USDT\n"
            "⏳ Your order is now queued for USDT transfer. The admin will complete the transfer to your wallet.",
            parse_mode="HTML",
            reply_markup=compact_reply_keyboard(lang),
        )
    except Exception:
        logger.exception("Failed to notify customer after payment confirmation")

    wallet_qr_id = order.get("wallet_qr_photo_id")
    admin_text = (
        "🚀 <b>تم تأكيد الدفع</b>\n\n"
        f"━━━ 👤 العميل ━━━\n"
        f"👤 الاسم: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 المعرف: <code>{order['telegram_id']}</code>\n"
        f"📱 المستخدم: @{html.escape(order['username'] or 'N/A')}\n\n"
        f"━━━ 💳 تفاصيل الطلب ━━━\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT\n"
        f"🌐 الشبكة: {html.escape(order['network'] or 'N/A')}\n"
        f"📍 عنوان المحفظة: <code>{html.escape(order['wallet_address'])}</code>\n\n"
        "اضغط على «إرسال USDT» بعد التنفيذ."
    )

    tasks = []
    for admin_id in Config.ADMIN_IDS:
        tasks.append(bot.send_message(
            admin_id, admin_text,
            reply_markup=order_admin_keyboard(order_id, "payment_confirmed"),
            parse_mode="HTML",
        ))
        if wallet_qr_id:
            tasks.append(bot.send_photo(
                admin_id, wallet_qr_id,
                caption=(
                    "📸 <b>QR لمحفظة العميل</b>\n"
                    f"🌐 الشبكة: {html.escape(order['network'] or 'N/A')}\n"
                    "يمكن استخدامه لتقليل أخطاء إدخال العنوان."
                ),
                parse_mode="HTML",
            ))
    await asyncio.gather(*tasks, return_exceptions=True)

    if wallet_qr_id:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET wallet_qr_photo_id = NULL WHERE id = $1", order_id)

    await callback.answer("✅ تم تأكيد الدفع!")
    await callback.message.edit_text(f"✅ تم تأكيد دفع الطلب #{order['order_number']}")
