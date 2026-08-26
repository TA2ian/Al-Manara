"""Authoritative Maintenance 2.0 administration flow."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard
from keyboards.maintenance import maintenance_confirm_keyboard, maintenance_mode_keyboard
from services.maintenance_service import MaintenanceMode, MaintenanceService

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _active_orders_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE status IN ('pending','waiting_payment','receipt_received','payment_confirmed')"
        )


_MODE_LABELS = {
    MaintenanceMode.OFF: "الوضع الطبيعي",
    MaintenanceMode.LIMITED: "الخدمة المحدودة",
    MaintenanceMode.MAINTENANCE: "الصيانة الكاملة",
    MaintenanceMode.EMERGENCY: "حالة الطوارئ",
}

_MODE_DESCRIPTIONS = {
    MaintenanceMode.OFF: "جميع الخدمات تعمل بشكل طبيعي.",
    MaintenanceMode.LIMITED: "تظل الخدمة متاحة، ويمكن للميزات التي تدعم هذا الوضع تقييد عمليات جديدة تدريجياً.",
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
        "<b>الصيانة الكاملة:</b> تمنع الطلبات الجديدة ولا تقطع الطلبات القائمة.\n"
        "<b>الطوارئ:</b> توقف تعامل المستخدمين مع الخدمة مؤقتاً.",
        parse_mode="HTML", reply_markup=maintenance_mode_keyboard(mode.value)
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
    mode = MaintenanceMode(raw)
    current = await MaintenanceService.get_mode()
    if mode == current:
        await callback.answer("هذا الوضع مفعّل بالفعل.", show_alert=True)
        return
    active_count = await _active_orders_count()
    warning = ""
    if mode == MaintenanceMode.MAINTENANCE and active_count:
        warning = f"\n\nℹ️ يوجد حالياً <b>{active_count}</b> طلب نشط. لن يتم قطعها؛ سيستمر lifecycle الخاص بها."
    if mode == MaintenanceMode.EMERGENCY and active_count:
        warning = f"\n\n⚠️ يوجد <b>{active_count}</b> طلب نشط. وضع الطوارئ سيمنع المستخدمين من متابعة التفاعل حتى يرفعه الأدمن. استخدمه فقط عند الحاجة."
    await callback.message.edit_text(
        f"⚠️ <b>تأكيد تغيير وضع التشغيل</b>\n\n"
        f"من: <b>{_MODE_LABELS[current]}</b>\n"
        f"إلى: <b>{_MODE_LABELS[mode]}</b>\n\n"
        f"{_MODE_DESCRIPTIONS[mode]}{warning}\n\n"
        "لن يتم تطبيق التغيير إلا بعد الضغط على زر التأكيد.",
        parse_mode="HTML", reply_markup=maintenance_confirm_keyboard(mode.value)
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

    await MaintenanceService.set_mode(target)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO audit_logs (admin_id, action, details, new_value, severity)
               VALUES ($1, $2, $3, $4, $5)""",
            callback.from_user.id,
            "maintenance_mode_changed",
            f"Maintenance mode changed from {current.value} to {target.value}",
            target.value,
            "critical" if target == MaintenanceMode.EMERGENCY else "warning" if target != MaintenanceMode.OFF else "info",
        )

    await callback.message.edit_text(
        f"{'🚨' if target == MaintenanceMode.EMERGENCY else '🛠️' if target == MaintenanceMode.MAINTENANCE else '🟡' if target == MaintenanceMode.LIMITED else '✅'} "
        f"<b>تم تغيير وضع التشغيل إلى {_MODE_LABELS[target]}</b>\n\n{_MODE_DESCRIPTIONS[target]}",
        parse_mode="HTML",
    )
    await callback.message.answer("⚙️ <b>لوحة التحكم</b>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
    await callback.answer("تم تطبيق التغيير")
