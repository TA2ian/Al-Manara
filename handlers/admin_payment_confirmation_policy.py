"""Admin payment-confirmation policy.

Owns the transition from receipt review to payment_confirmed.
The legacy admin.py handler remains as a compatibility fallback until the
remaining admin surface is fully decomposed.
"""
import asyncio
import html

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import order_admin_keyboard
from keyboards.reply import compact_reply_keyboard

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.callback_query(F.data.startswith("admin_confirm_payment_"))
async def confirm_payment(callback: CallbackQuery):
    """Confirm a customer's payment and move the order to payment_confirmed."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.replace("admin_confirm_payment_", "", 1))
    except (TypeError, ValueError):
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            """
            SELECT o.*, u.telegram_id, u.full_name, u.username, u.language
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE o.id = $1
            """,
            order_id,
        )

        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True)
            return

        # Do not allow an invalid/replayed callback to advance an unrelated state.
        if order["status"] != "receipt_received":
            await callback.answer(
                f"⚠️ حالة الطلب الحالية: {order['status']}",
                show_alert=True,
            )
            return

        await conn.execute(
            "UPDATE orders SET status = 'payment_confirmed' WHERE id = $1 AND status = 'receipt_received'",
            order_id,
        )

    pay_lang = order["language"] or "ar"
    bot = Bot(token=Config.BOT_TOKEN)

    # Tell the customer that payment has been verified and fulfillment is next.
    try:
        await bot.send_message(
            order["telegram_id"],
            f"✅ <b>تم تأكيد الدفع!</b>\n\n"
            f"📦 الطلب: #{order['order_number']}\n"
            f"💰 المبلغ: {order['amount_usdt']} USDT\n"
            f"🚀 جاري إرسال USDT إلى محفظتك...\n"
            f"⏱ يستغرق وصول USDT عادة من 5-30 دقيقة حسب شبكة التحويل.",
            parse_mode="HTML",
            reply_markup=compact_reply_keyboard(pay_lang),
        )
    except Exception:
        # Customer notification failure must not roll the order back.
        pass

    admin_text = (
        f"🚀 <b>تم تأكيد الدفع</b>\n\n"
        f"━━━ 👤 العميل ━━━\n"
        f"👤 الاسم: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 المعرف: <code>{order['telegram_id']}</code>\n"
        f"📱 المستخدم: @{html.escape(order['username'] or 'N/A')}\n\n"
        f"━━━ 💳 تفاصيل الطلب ━━━\n"
        f"📦 الطلب: #{order['order_number']}\n"
        f"💰 المبلغ: {order['amount_usdt']} USDT\n"
        f"🌐 الشبكة: {order['network']}\n"
        f"📍 عنوان المحفظة: <code>{html.escape(order['wallet_address'])}</code>\n\n"
        f"اضغط على 'إرسال USDT' بعد التنفيذ:"
    )

    wallet_qr_id = order.get("wallet_qr_photo_id")
    tasks = []
    for admin_id in Config.ADMIN_IDS:
        tasks.append(
            bot.send_message(
                admin_id,
                admin_text,
                reply_markup=order_admin_keyboard(order_id, "payment_confirmed"),
                parse_mode="HTML",
            )
        )
        if wallet_qr_id:
            tasks.append(
                bot.send_photo(
                    admin_id,
                    wallet_qr_id,
                    caption=(
                        "📸 <b>QR code لعنوان محفظة العميل</b> — "
                        f"{html.escape(order['full_name'] or 'N/A')}\n"
                        f"🌐 الشبكة: {html.escape(order['network'] or 'N/A')}\n"
                        "يمكن مسحه ضوئياً لإرسال USDT إلى عنوان العميل بدون خطأ"
                    ),
                    parse_mode="HTML",
                )
            )

    await asyncio.gather(*tasks, return_exceptions=True)

    # The QR has been delivered to admins; remove the temporary DB reference.
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET wallet_qr_photo_id = NULL WHERE id = $1",
            order_id,
        )

    await callback.answer("✅ تم تأكيد الدفع!")
    await callback.message.edit_text(
        f"✅ تم تأكيد دفع الطلب #{order['order_number']}"
    )
