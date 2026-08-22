"""Authoritative admin rejection flows for orders and payment receipts."""
import html
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard, receipt_upload_keyboard
from keyboards.reply import compact_reply_keyboard

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.callback_query(F.data.startswith("admin_reject_receipt_"))
async def reject_receipt(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    order_id = int(callback.data.replace("admin_reject_receipt_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name, u.language FROM orders o "
            "JOIN users u ON o.user_id = u.id WHERE o.id = $1", order_id,
        )
        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True); return
        if order["status"] != "receipt_received":
            await callback.answer("لا يمكن رفض الإيصال من الحالة الحالية", show_alert=True); return
        await conn.execute("UPDATE orders SET status = 'waiting_payment' WHERE id = $1", order_id)

    remaining = ""
    if order["payment_deadline"]:
        seconds = int((order["payment_deadline"] - datetime.now()).total_seconds())
        if seconds > 0:
            remaining = f"⏱ الوقت المتبقي: <b>{seconds // 60} دقيقة و{seconds % 60} ثانية</b>"
    bot = Bot(token=Config.BOT_TOKEN)
    try:
        await bot.send_message(
            order["telegram_id"],
            "⚠️ <b>تم رفض الإيصال</b>\n\n"
            f"عذراً {html.escape(order['full_name'] or 'عميلنا العزيز')}، الإيصال غير مطابق أو غير واضح.\n\n"
            "📌 أرسل إيصالاً جديداً يظهر المبلغ واسم المستفيد والتاريخ.\n\n"
            f"📎 اضغط لإعادة رفع الإيصال.\n{remaining}\n\n"
            "⚠️ إذا انتهت المهلة سيتم إلغاء الطلب تلقائياً.",
            reply_markup=receipt_upload_keyboard(order_id), parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to notify receipt rejection for order %s", order_id)
    await callback.answer("❌ تم رفض الإيصال!")
    await callback.message.edit_text(f"❌ تم رفض إيصال الطلب #{order['order_number']}", parse_mode="HTML")
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_reject_"), ~F.data.startswith("admin_reject_receipt_"))
async def reject_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    order_id = int(callback.data.replace("admin_reject_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id AS user_tg, u.full_name, u.language FROM orders o "
            "JOIN users u ON o.user_id = u.id WHERE o.id = $1", order_id,
        )
        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True); return
        if order["status"] not in ("pending", "waiting_payment", "receipt_received"):
            await callback.answer("لا يمكن رفض الطلب من حالته الحالية", show_alert=True); return
        await conn.execute(
            "UPDATE orders SET status = 'rejected', wallet_qr_photo_id = NULL, receipt_photo_id = NULL WHERE id = $1",
            order_id,
        )
    bot = Bot(token=Config.BOT_TOKEN)
    try:
        lang = order["language"] or "ar"
        text = (
            f"❌ <b>تم رفض طلبك</b>\n\n📦 الطلب: #{order['order_number']}\n💰 المبلغ: {order['amount_usdt']} USDT\n\nيمكنك إنشاء طلب جديد من القائمة السفلية."
        ) if lang == "ar" else (
            f"❌ <b>Your order was rejected</b>\n\n📦 Order: #{order['order_number']}\n💰 Amount: {order['amount_usdt']} USDT\n\nYou can create a new order from the bottom menu."
        )
        await bot.send_message(order["user_tg"], text, parse_mode="HTML", reply_markup=compact_reply_keyboard(lang))
    except Exception:
        logger.exception("Failed to notify order rejection for %s", order_id)
    await callback.answer("❌ تم رفض الطلب!")
    await callback.message.edit_text(f"❌ تم رفض الطلب #{order['order_number']}", parse_mode="HTML")
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_noop"))
async def admin_noop(callback: CallbackQuery):
    await callback.answer("⏳ الطلب في انتظار الدفع من العميل...", show_alert=True)
