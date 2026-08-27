"""Authoritative Maintenance 2.0 administration flow."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from keyboards.admin import enhanced_admin_menu_keyboard
from keyboards.maintenance import maintenance_confirm_keyboard, maintenance_mode_keyboard
from services.admin_access_service import AdminAccessService
from services.maintenance_service import MaintenanceMode, MaintenanceService
from database import get_pool

router = Router()


def is_admin(user_id: int | None) -> bool:
    return AdminAccessService.is_admin(user_id)


async def _active_orders_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status IN ('pending','waiting_payment','receipt_received','payment_confirmed')")


_MODE_LABELS = {
    MaintenanceMode.OFF: "الوضع الطبيعي",
    MaintenanceMode.LIMITED: "الخدمة المحدودة",
    MaintenanceMode.MAINTENANCE: "الصيانة الكاملة",
    MaintenanceMode.EMERGENCY: "حالة الطوارئ",
}

_MODE_DESCRIPTIONS = {
    MaintenanceMode.OFF: "جميع الخدمات تعمل بشكل طبيعي.",
    MaintenanceMode.LIMITED: "الخدمة تبقى متاحة، مع إمكانية تقييد بعض العمليات غير الأساسية تدريجياً.",
    MaintenanceMode.MAINTENANCE: "يتم إيقاف العمليات الجديدة فقط. الطلبات الحالية تبقى محفوظة وتستمر في دورة حياتها.",
    MaintenanceMode.EMERGENCY: "توقف تشغيلي شامل للمستخدمين لمعالجة مشكلة عاجلة. الإدارة تبقى متاحة.",
}


@router.callback_query(F.data == "admin_maintenance")
async def admin_maintenance(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    mode = await MaintenanceService.get_mode()
    active_count = await _active_orders_count()
    await callback.message.edit_text(
        "🛠️ <b>إدارة وضع التشغيل</b>\n\n"
        f"الحالة الحالية: <b>{_MODE_LABELS[mode]}</b>\n"
        f"الطلبات النشطة: <b>{active_count}</b>\n\n"
        "اختر الوضع المطلوب. لن يتم تنفيذ أي تغيير من هذه الشاشة مباشرة؛ ستظهر خطوة تأكيد مستقلة.\n\n"
        "<b>الخدمة المحدودة:</b> تسمح بالتشغيل مع تقييد الوظائف غير الأساسية عند الحاجة.\n"
        "<b>الصيانة الكاملة:</b> تمنع العمليات الجديدة ولا تقطع الطلبات القائمة.\n"
        "<b>الطوارئ:</b> توقف تفاعل المستخدمين مؤقتاً لمعالجة حالة عاجلة.",
        parse_mode="HTML", reply_markup=maintenance_mode_keyboard(mode.value),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_maintenance_mode_"))
async def choose_maintenance_mode(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    raw = callback.data.removeprefix("admin_maintenance_mode_")
    if raw not in {mode.value for mode in MaintenanceMode}:
        await callback.answer("❌ وضع غير صالح", show_alert=True)
        return
    target = MaintenanceMode(raw)
    current = await MaintenanceService.get_mode()
    if target == current:
        await callback.answer("هذا الوضع مفعّل بالفعل.", show_alert=True)
        return
    active_count = await _active_orders_count()
    warning = ""
    if target == MaintenanceMode.MAINTENANCE and active_count:
        warning = f"\n\nℹ️ يوجد حالياً <b>{active_count}</b> طلب نشط. لن يتم قطعها؛ سيستمر lifecycle الخاص بها."
    elif target == MaintenanceMode.EMERGENCY and active_count:
        warning = f"\n\n⚠️ يوجد <b>{active_count}</b> طلب نشط. وضع الطوارئ سيمنع المستخدمين من متابعة التفاعل حتى يرفعه الأدمن. استخدمه فقط عند الحاجة."
    await callback.message.edit_text(
        f"⚠️ <b>تأكيد تغيير وضع التشغيل</b>\n\nمن: <b>{_MODE_LABELS[current]}</b>\nإلى: <b>{_MODE_LABELS[target]}</b>\n\n"
        f"{_MODE_DESCRIPTIONS[target]}{warning}\n\nلن يتم تطبيق التغيير إلا بعد الضغط على زر التأكيد.",
        parse_mode="HTML", reply_markup=maintenance_confirm_keyboard(target.value),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_maintenance_confirm_"))
async def confirm_maintenance_mode(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    raw = callback.data.removeprefix("admin_maintenance_confirm_")
    if raw not in {mode.value for mode in MaintenanceMode}:
        await callback.answer("❌ وضع غير صالح", show_alert=True)
        return
    target = MaintenanceMode(raw)
    current = await MaintenanceService.get_mode()
    if target == current:
        await callback.answer("لم يتغير الوضع.", show_alert=True)
        return

    applied = await MaintenanceService.set_mode(target, admin_id=callback.from_user.id)
    if applied != target:
        await callback.answer("تعذر تطبيق التغيير؛ أعد فتح لوحة الصيانة.", show_alert=True)
        return

    stats = await MaintenanceService.notification_stats(target)
    icon = "🚨" if target == MaintenanceMode.EMERGENCY else "🛠️" if target == MaintenanceMode.MAINTENANCE else "🟡" if target == MaintenanceMode.LIMITED else "✅"
    await callback.message.edit_text(
        f"{icon} <b>تم تغيير وضع التشغيل إلى {_MODE_LABELS[target]}</b>\n\n"
        f"{_MODE_DESCRIPTIONS[target]}\n\n"
        "📨 <b>تم وضع إشعارات المستخدمين في طابور الإرسال.</b>\n"
        f"⏳ بانتظار الإرسال: <b>{stats['queued']}</b>\n"
        f"✅ أُرسلت سابقاً: <b>{stats['sent']}</b>\n"
        f"❌ فشل نهائي: <b>{stats['failed']}</b>",
        parse_mode="HTML",
    )
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=enhanced_admin_menu_keyboard(), parse_mode="HTML")
    await callback.answer("تم تطبيق التغيير ووضع الإشعارات في الطابور")
