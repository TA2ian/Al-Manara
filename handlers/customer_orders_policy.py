"""Customer order-history display policy."""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

from keyboards.inline import orders_pagination_keyboard, receipt_upload_keyboard
from services.locale_service import locale_service
from services.notification_service import NotificationService
from services.formatters import usdt
from database import get_pool
from config import Config

router = Router()
PAGE_SIZE = 5

AR_STATUS = {
    "pending": "⏳ بانتظار موافقة الإدارة",
    "waiting_payment": "💳 بانتظار دفع المبلغ ورفع الإيصال",
    "receipt_received": "📎 تم استلام الإيصال — بانتظار مراجعة الإدارة",
    "payment_confirmed": "🚀 تم تأكيد الدفع — بانتظار إرسال USDT من الإدارة",
    "completed": "✅ اكتمل الطلب وتم إرسال USDT",
    "rejected": "❌ تم رفض الطلب",
    "expired": "⌛ انتهت صلاحية الطلب",
}

EN_STATUS = {
    "pending": "⏳ Awaiting admin approval",
    "waiting_payment": "💳 Awaiting payment and receipt upload",
    "receipt_received": "📎 Receipt received — awaiting admin review",
    "payment_confirmed": "🚀 Payment confirmed — awaiting USDT transfer by admin",
    "completed": "✅ Completed and USDT sent",
    "rejected": "❌ Order rejected",
    "expired": "⌛ Order expired",
}


async def _render_page(user_id: int, lang: str, page: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE user_id = $1", user_id)
        if not total:
            return None, 0, []
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_pages))
        orders = await conn.fetch(
            "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            user_id, PAGE_SIZE, (page - 1) * PAGE_SIZE,
        )

    status_map = AR_STATUS if lang == "ar" else EN_STATUS
    title = "📋 <b>طلباتي</b>" if lang == "ar" else "📋 <b>My Orders</b>"
    lines = [f"{title} — ({page}/{total_pages})"]

    for order in orders:
        status = status_map.get(order["status"], order["status"])
        lines.append(
            "\n━━━━━━━━━━━━━━━\n"
            f"📦 <b>#{order['order_number']}</b>\n"
            f"💰 {usdt(order['amount_usdt'])} USDT ({order['network']})\n"
            f"📊 <b>{status}</b>\n"
            f"📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )

    return "\n".join(lines), total_pages, orders


async def _get_user(message_or_callback):
    telegram_id = message_or_callback.from_user.id
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await pool.fetchrow("SELECT id, language FROM users WHERE telegram_id = $1", telegram_id)


async def _repair_waiting_payment_visibility(message: Message, order, lang: str):
    if order["status"] != "waiting_payment" or order.get("customer_status_message_id"):
        return False
    try:
        bot = Bot(token=Config.BOT_TOKEN)
        notification = NotificationService(bot, Config.ADMIN_IDS)
        delivered = await notification.notify_order_approved(message.from_user.id, dict(order), lang=lang)
        if not delivered:
            return False
        prompt = (
            f"📎 <b>#{order['order_number']}</b> — أرسل إيصال الدفع عند إتمام التحويل:"
            if lang == "ar" else
            f"📎 <b>#{order['order_number']}</b> — upload your payment receipt after the transfer:"
        )
        prompt_message = await message.answer(prompt, parse_mode="HTML", reply_markup=receipt_upload_keyboard(order["id"], lang))
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET customer_status_message_id = $1 WHERE id = $2", prompt_message.message_id, order["id"])
        return True
    except Exception:
        return False


@router.message(F.text.in_(["📋 طلباتي", "📋 Orders"]))
async def show_precise_orders(message: Message):
    user = await _get_user(message)
    if not user:
        await message.answer("يرجى بدء البوت أولاً: /start")
        return
    lang = user["language"] or "ar"
    text, total_pages, orders = await _render_page(user["id"], lang, 1)
    if not orders:
        await message.answer(locale_service.get("no_orders", lang))
        return
    await message.answer(text, parse_mode="HTML", reply_markup=orders_pagination_keyboard(1, total_pages, lang))
    for order in orders:
        if order["status"] == "waiting_payment":
            repaired = await _repair_waiting_payment_visibility(message, order, lang)
            if not repaired:
                prompt = (
                    f"📎 <b>#{order['order_number']}</b> — أرسل إيصال الدفع عند إتمام التحويل:"
                    if lang == "ar" else
                    f"📎 <b>#{order['order_number']}</b> — upload your payment receipt after the transfer:"
                )
                await message.answer(prompt, parse_mode="HTML", reply_markup=receipt_upload_keyboard(order["id"], lang))


@router.callback_query(F.data.startswith("orders_page_"))
async def show_precise_orders_page(callback: CallbackQuery):
    try:
        page = int(callback.data.replace("orders_page_", ""))
    except (TypeError, ValueError):
        await callback.answer("❌ صفحة غير صالحة", show_alert=True)
        return
    user = await _get_user(callback)
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    lang = user["language"] or "ar"
    text, total_pages, orders = await _render_page(user["id"], lang, page)
    if not orders:
        await callback.answer("📭 لا توجد طلبات", show_alert=True)
        return
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=orders_pagination_keyboard(page, total_pages, lang))
    await callback.answer()


@router.callback_query(F.data == "close_orders_list")
async def close_orders_list(callback: CallbackQuery):
    """Close the customer order-history message without changing order state."""
    user = await _get_user(callback)
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return

    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)

    await callback.answer("تم إغلاق قائمة الطلبات." if (user["language"] or "ar") == "ar" else "Order list closed.")
