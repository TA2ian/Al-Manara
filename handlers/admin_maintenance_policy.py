"""Authoritative admin maintenance-mode policy."""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from config import Config
from database import get_pool
from services.locale_service import locale_service
from services.settings_service import SettingsService
from keyboards.inline import admin_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _notify_users_maintenance(admin_msg: Message, locale_key: str = "maintenance_notification"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT telegram_id, language FROM users WHERE terms_accepted = TRUE")
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    sent = failed = 0
    for user in users:
        try:
            await bot.send_message(
                user["telegram_id"],
                locale_service.get(locale_key, user["language"] or "ar"),
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1
    await admin_msg.answer(
        f"📨 <b>إشعار الصيانة للمستخدمين</b>\n\n✅ تم الإشعار: {sent}\n❌ فشل: {failed}\n📊 المجموع: {len(users)}",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_maintenance")
async def admin_maintenance(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    if Config.get_maintenance_mode():
        await SettingsService.set_bool("maintenance_mode", False)
        Config.set_maintenance_mode_sync(False)
        await callback.message.edit_text(
            "✅ <b>تم إيقاف وضع الصيانة</b>\n\nالبوت متاح للمستخدمين الآن.",
            parse_mode="HTML",
        )
        await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
        await callback.answer()
        await _notify_users_maintenance(callback.message, "maintenance_ended")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        active_orders = await conn.fetch(
            "SELECT o.order_number, o.status, o.amount_usdt, u.full_name "
            "FROM orders o JOIN users u ON o.user_id = u.id "
            "WHERE o.status IN ('pending','waiting_payment','receipt_received','payment_confirmed') "
            "ORDER BY o.created_at ASC"
        )

    if active_orders:
        labels = {
            "pending": "⏳ قيد الانتظار",
            "waiting_payment": "💳 انتظار الدفع",
            "receipt_received": "📎 قيد المراجعة",
            "payment_confirmed": "🚀 انتظار الإرسال",
        }
        lines = [
            f"• #{row['order_number']} — {labels.get(row['status'], row['status'])} — {row['full_name'] or 'N/A'} — {row['amount_usdt']} USDT"
            for row in active_orders[:10]
        ]
        if len(active_orders) > 10:
            lines.append(f"... و{len(active_orders) - 10} طلب آخر")
        await callback.message.edit_text(
            "⛔ <b>لا يمكن تفعيل وضع الصيانة</b>\n\n"
            f"يوجد <b>{len(active_orders)}</b> طلب نشط يجب إكمالها أولاً:\n\n"
            + "\n".join(lines),
            parse_mode="HTML",
        )
        await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
        await callback.answer()
        return

    await SettingsService.set_bool("maintenance_mode", True)
    Config.set_maintenance_mode_sync(True)
    await callback.message.edit_text(
        "🛑 <b>تم تفعيل وضع الصيانة</b>\n\n"
        "جميع الطلبات مكتملة. المستخدمون سيرون رسالة الصيانة، والمشرفون ما زالوا قادرين على الوصول.",
        parse_mode="HTML",
    )
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
    await callback.answer()
    await _notify_users_maintenance(callback.message)


@router.callback_query(F.data == "admin_maintenance_force")
async def admin_maintenance_force(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await SettingsService.set_bool("maintenance_mode", True)
    Config.set_maintenance_mode_sync(True)
    await callback.message.edit_text(
        "🛑 <b>تم تفعيل وضع الصيانة (قسري)</b>\n\n⚠️ تم تجاوز الطلبات النشطة.",
        parse_mode="HTML",
    )
    await callback.answer()
    await _notify_users_maintenance(callback.message)
