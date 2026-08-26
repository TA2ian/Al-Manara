"""Authoritative admin utility flows."""
import html
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram import Bot

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard, auto_approve_keyboard, order_detail_keyboard
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.callback_query(F.data.startswith("rate_"))
async def handle_rating(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer()
        return
    try:
        rating = int(parts[1])
        order_id = int(parts[2])
    except ValueError:
        await callback.answer("❌ تقييم غير صالح", show_alert=True)
        return
    if rating < 1 or rating > 5:
        await callback.answer("❌ تقييم غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.order_number, o.amount_usdt, o.network, u.full_name, u.telegram_id, u.username "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )
        if not order or order["telegram_id"] != callback.from_user.id:
            await callback.answer("❌ التقييم غير صالح لهذا الحساب.", show_alert=True)
            return
        await conn.execute("UPDATE orders SET customer_rating = $1 WHERE id = $2", rating, order_id)
        await conn.execute(
            "INSERT INTO audit_logs (user_id, action, details, new_value, severity) VALUES "
            "((SELECT user_id FROM orders WHERE id = $1), 'customer_rating', $2, $3, 'info')",
            order_id, f"Order {order['order_number']} customer rating", str(rating),
        )

    await callback.message.edit_text(f"🙏 شكراً لتقييمك ({'⭐' * rating})!", parse_mode="HTML")
    await callback.answer("✅ تم حفظ التقييم!")
    bot = Bot(token=Config.BOT_TOKEN)
    admin_msg = (
        "⭐ <b>تقييم جديد!</b>\n\n"
        f"👤 الاسم: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 <code>{order['telegram_id']}</code>\n"
        f"📱 المستخدم: @{html.escape(order['username'] or 'N/A')}\n\n"
        f"📦 الطلب: #{html.escape(order['order_number'])}\n"
        f"💰 {order['amount_usdt']} USDT\n"
        f"🌐 {html.escape(order['network'] or '')}\n\n"
        f"🏆 {'⭐' * rating} ({rating}/5)"
    )
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_msg, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send rating to admin %s", admin_id)


@router.callback_query(F.data == "admin_auto_approve")
async def admin_auto_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    enabled = await SettingsService.get_bool("auto_approve", False)
    await callback.message.edit_text(
        "⭐ <b>التوثيق التلقائي للعملاء الموثوقين</b>\n\n"
        "عند تفعيل هذه الخاصية، يتم اعتماد طلبات العملاء الذين أكملوا 3 طلبات أو أكثر سابقة تلقائياً دون انتظار موافقة المشرف.\n\n"
        f"الحالة: {'🟢 مفعل' if enabled else '🔴 معطل'}",
        reply_markup=auto_approve_keyboard(enabled),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_auto_approve_toggle")
async def admin_auto_approve_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    current = await SettingsService.get_bool("auto_approve", False)
    await SettingsService.set_bool("auto_approve", not current)
    await callback.message.edit_text(
        f"✅ {'تم تفعيل' if not current else 'تم إيقاف'} التوثيق التلقائي!\n\n"
        f"{'سيتم اعتماد طلبات العملاء الموثوقين تلقائياً.' if not current else 'سيحتاج جميع العملاء إلى موافقة يدوية.'}",
        parse_mode="HTML",
    )
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_timeline_"))
async def admin_order_timeline(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    try:
        order_id = int(callback.data.replace("admin_timeline_", ""))
    except ValueError:
        await callback.answer("❌ الطلب غير صالح", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.full_name, u.telegram_id AS user_tg FROM orders o "
            "JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )
        if not order:
            await callback.answer("❌ الطلب غير موجود", show_alert=True)
            return
        logs = await conn.fetch(
            "SELECT action, details, previous_value, new_value, timestamp FROM audit_logs "
            "WHERE details LIKE $1 ORDER BY timestamp ASC, id ASC",
            f"%{order['order_number']}%",
        )

    status_icons = {"pending": "🔄", "waiting_payment": "💳", "receipt_received": "📎", "payment_confirmed": "✅", "completed": "🎉", "rejected": "❌", "expired": "⌛"}
    status_names = {"pending": "تم إنشاء الطلب", "waiting_payment": "بانتظار الدفع", "receipt_received": "تم استلام الإيصال", "payment_confirmed": "تم تأكيد الدفع", "completed": "مكتمل", "rejected": "مرفوض", "expired": "منتهي"}
    icons = {"approve": "✅", "reject": "❌", "confirm_payment": "💸", "send_usdt": "🚀", "note": "📝", "expire": "⌛", "setting_update": "⚙️", "customer_rating": "⭐"}
    timeline = [f"🆕 <b>تم إنشاء الطلب</b> — {order['created_at'].strftime('%Y-%m-%d %H:%M')}"]
    for log in logs:
        ts = log["timestamp"].strftime("%Y-%m-%d %H:%M") if log["timestamp"] else ""
        line = f"{icons.get(log['action'], '📌')} <b>{html.escape(str(log['action']).replace('_', ' ').title())}</b> — {ts}"
        if log["new_value"]:
            line += f" — <code>{html.escape(str(log['new_value']))}</code>"
        timeline.append(line)
    timeline.append(f"{status_icons.get(order['status'], '❓')} <b>الحالية: {status_names.get(order['status'], order['status'])}</b>")
    if order["completed_at"]:
        timeline.append(f"🎉 <b>مكتمل</b> — {order['completed_at'].strftime('%Y-%m-%d %H:%M')}")

    wallet = html.escape(order["wallet_address"] or "")
    text = f"📋 <b>سجل الطلب #{html.escape(order['order_number'])}</b>\n━━━━━━━━━━━━━━\n" + "\n".join(timeline) + f"\n━━━━━━━━━━━━━━\n📍 <code>{wallet[:15]}...</code>"
    await callback.message.edit_text(text, reply_markup=order_detail_keyboard(order_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        logs = await conn.fetch(
            """SELECT action, details, previous_value, new_value, severity, timestamp
               FROM audit_logs ORDER BY timestamp DESC, id DESC LIMIT 30"""
        )
    if not logs:
        text = "📝 <b>السجلات</b>\n\nلا توجد سجلات تشغيلية بعد."
    else:
        lines = ["📝 <b>آخر السجلات التشغيلية</b>", ""]
        for log in logs:
            ts = log["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if log["timestamp"] else ""
            action = html.escape(str(log["action"]))
            details = html.escape(str(log["details"] or ""))
            value = html.escape(str(log["new_value"])) if log["new_value"] else ""
            lines.append(f"• <b>{ts}</b> — <code>{action}</code> — {details}" + (f" → <code>{value}</code>" if value else ""))
        text = "\n".join(lines)
    await callback.message.edit_text(text[:3900], reply_markup=admin_menu_keyboard(), parse_mode="HTML")
    await callback.answer()
