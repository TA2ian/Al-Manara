"""Authoritative admin maintenance-mode policy."""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from config import Config
from database import get_pool
from services.locale_service import locale_service
from services.settings_service import SettingsService
from keyboards.inline import admin_menu_keyboard, maintenance_confirmation_keyboard

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
            await bot.send_message(user["telegram_id"], locale_service.get(locale_key, user["language"] or "ar"), parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await admin_msg.answer(f"📨 <b>إشعار الصيانة للمستخدمين</b>\n\n✅ تم الإشعار: {sent}\n❌ فشل: {failed}\n📊 المجموع: {len(users)}", parse_mode="HTML")


async def _active_orders():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT o.order_number, o.status, o.amount_usdt, u.full_name FROM orders o JOIN users u ON o.user_id = u.id "
            "WHERE o.status IN ('pending','waiting_payment','receipt_received','payment_confirmed') ORDER BY o.created_at ASC"
        )


@router.callback_query(F.data == "admin_maintenance")
async def admin_maintenance(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    enabled = Config.get_maintenance_mode()
    if enabled:
        await callback.message.edit_text(
            "⚠️ <b>وضع الصيانة مفعّل حالياً</b>\n\n"
            "سيتم السماح بعودة المستخدمين إلى الخدمات بعد تأكيد الإيقاف.\n\nهل تريد إيقاف وضع الصيانة؟",
            reply_markup=maintenance_confirmation_keyboard(True), parse_mode="HTML",
        )
        await callback.answer()
        return

    active_orders = await _active_orders()
    if active_orders:
        labels = {"pending": "⏳ قيد الانتظار", "waiting_payment": "💳 انتظار الدفع", "receipt_received": "📎 قيد المراجعة", "payment_confirmed": "🚀 انتظار الإرسال"}
        lines = [f"• #{row['order_number']} — {labels.get(row['status'], row['status'])} — {row['full_name'] or 'N/A'} — {row['amount_usdt']} USDT" for row in active_orders[:10]]
        if len(active_orders) > 10:
            lines.append(f"... و{len(active_orders) - 10} طلب آخر")
        await callback.message.edit_text(
            "⛔ <b>لا يمكن تفعيل وضع الصيانة الآن</b>\n\n"
            f"يوجد <b>{len(active_orders)}</b> طلب نشط. يجب إنهاؤها أولاً قبل الدخول في وضع الصيانة.\n\n" + "\n".join(lines),
            reply_markup=admin_menu_keyboard(), parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "⚠️ <b>تأكيد تفعيل وضع الصيانة</b>\n\n"
        "سيتم منع المستخدمين من بدء العمليات الجديدة، مع إبقاء صلاحيات الإدارة متاحة.\n"
        "سيتم تسجيل عملية التفعيل وإشعار المستخدمين بعد التنفيذ.\n\n"
        "هل تريد المتابعة؟",
        reply_markup=maintenance_confirmation_keyboard(False), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_maintenance_confirm_on")
async def confirm_maintenance_on(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    active_orders = await _active_orders()
    if active_orders:
        await callback.answer("⛔ ظهرت طلبات نشطة؛ لم يتم تفعيل الصيانة.", show_alert=True)
        await callback.message.edit_text("⛔ <b>تم إلغاء التفعيل</b>\n\nهناك طلبات نشطة. يجب إكمالها أولاً.", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
        return
    await SettingsService.set_bool("maintenance_mode", True)
    Config.set_maintenance_mode_sync(True)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO audit_logs (admin_id, action, details, new_value, severity) VALUES ($1, 'maintenance_enabled', 'Maintenance mode enabled', 'on', 'warning')", callback.from_user.id)
    await callback.message.edit_text("🛑 <b>تم تفعيل وضع الصيانة</b>\n\nالمستخدمون لن يتمكنوا من بدء عمليات جديدة، ويمكن للإدارة متابعة العمل.", parse_mode="HTML")
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
    await callback.answer("تم تفعيل الصيانة")
    await _notify_users_maintenance(callback.message)


@router.callback_query(F.data == "admin_maintenance_confirm_off")
async def confirm_maintenance_off(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await SettingsService.set_bool("maintenance_mode", False)
    Config.set_maintenance_mode_sync(False)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO audit_logs (admin_id, action, details, new_value, severity) VALUES ($1, 'maintenance_disabled', 'Maintenance mode disabled', 'off', 'info')", callback.from_user.id)
    await callback.message.edit_text("✅ <b>تم إيقاف وضع الصيانة</b>\n\nالبوت متاح للمستخدمين الآن.", parse_mode="HTML")
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
    await callback.answer("تم إيقاف الصيانة")
    await _notify_users_maintenance(callback.message, "maintenance_ended")
