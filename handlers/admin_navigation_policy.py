"""Authoritative admin navigation and analytics."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from keyboards.inline import admin_menu_keyboard
from services.analytics_service import AnalyticsService
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء والعودة للوحة التحكم", callback_data="admin_cancel_input")]
        ]
    )


def _format_hours(value) -> str:
    hours = float(value or 0)
    if hours < 1:
        return f"{hours * 60:.0f} دقيقة"
    return f"{hours:.1f} ساعة"


async def _show_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_cancel_input")
async def cancel_admin_input(callback: CallbackQuery, state: FSMContext):
    """Cancel any unfinished admin text-entry flow."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_admin_menu(callback, state)
    await callback.answer("تم الإلغاء")


@router.callback_query(F.data == "admin_dashboard")
async def financial_dashboard(callback: CallbackQuery):
    """Show the operational financial dashboard."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    data = await AnalyticsService.dashboard()
    periods = data["periods"]
    labels = {
        "pending": "⏳ معلقة",
        "waiting_payment": "💳 بانتظار الدفع",
        "receipt_received": "📎 الإيصالات للمراجعة",
        "payment_confirmed": "✅ الدفع مؤكد",
    }
    state_lines = [
        f"{labels.get(row['status'], row['status'])}: <b>{row['count']}</b> — {row['usdt']:,.2f} USDT"
        for row in data["states"]
    ]
    state_text = "\n".join(state_lines) if state_lines else "لا توجد طلبات نشطة"

    text = (
        "📊 <b>لوحة الأداء المالي</b>\n\n"
        "━━━ اليوم ━━━\n"
        f"📦 الطلبات: <b>{periods['today_orders']}</b>\n"
        f"✅ المكتمل: <b>{periods['today_completed']}</b>\n"
        f"💰 USDT: <b>{periods['today_usdt']:,.2f}</b>\n"
        f"💵 الرسوم: <b>{periods['today_fees']:,.2f}</b>\n\n"
        "━━━ آخر 7 أيام ━━━\n"
        f"📦 الطلبات: <b>{periods['week_orders']}</b>\n"
        f"✅ المكتمل: <b>{periods['week_completed']}</b>\n"
        f"💰 USDT: <b>{periods['week_usdt']:,.2f}</b>\n"
        f"💵 الرسوم: <b>{periods['week_fees']:,.2f}</b>\n\n"
        "━━━ هذا الشهر ━━━\n"
        f"📦 الطلبات: <b>{periods['month_orders']}</b>\n"
        f"✅ المكتمل: <b>{periods['month_completed']}</b>\n"
        f"💵 الرسوم: <b>{periods['month_fees']:,.2f}</b>\n"
        f"💰 USDT: <b>{periods['month_usdt']:,.2f}</b>\n\n"
        "━━━ الطلبات النشطة ━━━\n"
        f"{state_text}\n\n"
        f"⌛ منتهية اليوم: <b>{data['expired_today']}</b>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📈 التحليل المالي", callback_data="admin_analytics")],
                [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_analytics")
async def financial_analytics(callback: CallbackQuery, state: FSMContext):
    """Show centralized financial and operational analytics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    await state.clear()
    data = await AnalyticsService.financial()
    summary = data["summary"]
    today = data["today"]
    users = data["users"]

    total_orders = int(summary["total_orders"] or 0)
    completed_orders = int(summary["completed_orders"] or 0)
    completion_rate = (completed_orders / total_orders * 100) if total_orders else 0

    currency_lines = [
        f"• {row['payment_currency']}: {row['count']} طلب — {row['total_amount']:,.2f} — {row['usdt']:,.2f} USDT"
        for row in data["currencies"]
    ]
    currency_text = "\n".join(currency_lines) if currency_lines else "• لا توجد بيانات مكتملة بعد"

    network_lines = [
        f"• {row['network']}: {row['count']} طلب — {row['usdt']:,.2f} USDT"
        for row in data["networks"]
    ]
    network_text = "\n".join(network_lines) if network_lines else "• لا توجد بيانات مكتملة بعد"

    text = (
        "📈 <b>التحليل المالي والتشغيلي</b>\n\n"
        "━━━ الأداء الكلي ━━━\n"
        f"📦 إجمالي الطلبات: <b>{total_orders}</b>\n"
        f"✅ مكتملة: <b>{completed_orders}</b>\n"
        f"📊 معدل الإكمال: <b>{completion_rate:.1f}%</b>\n"
        f"❌ مرفوضة: <b>{summary['rejected_orders']}</b>\n"
        f"⌛ منتهية: <b>{summary['expired_orders']}</b>\n"
        f"💰 USDT المسلم: <b>{summary['completed_usdt']:,.2f}</b>\n"
        f"💵 الرسوم المحققة: <b>{summary['completed_fees']:,.2f}</b>\n\n"
        "━━━ التشغيل الحالي ━━━\n"
        f"⏳ الطلبات النشطة: <b>{summary['active_orders']}</b>\n"
        f"💰 قيمتها: <b>{summary['active_usdt']:,.2f} USDT</b>\n"
        f"⏱ متوسط إتمام الطلب: <b>{_format_hours(summary['average_completion_hours'])}</b>\n"
        f"⭐ متوسط تقييم العملاء: <b>{float(summary['average_rating'] or 0):.2f}/5</b>\n\n"
        "━━━ اليوم المكتمل ━━━\n"
        f"📦 الطلبات: <b>{today['completed_orders']}</b>\n"
        f"💰 USDT: <b>{today['usdt']:,.2f}</b>\n"
        f"💵 الرسوم: <b>{today['fees']:,.2f}</b>\n\n"
        "━━━ العملاء ━━━\n"
        f"👤 إجمالي العملاء: <b>{users['total_users']}</b>\n"
        f"🆕 جدد اليوم: <b>{users['new_today']}</b>\n"
        f"📅 جدد خلال 30 يوماً: <b>{users['new_30d']}</b>\n\n"
        "━━━ حسب عملة الدفع ━━━\n"
        f"{currency_text}\n\n"
        "━━━ حسب الشبكة ━━━\n"
        f"{network_text}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")]
            ]
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_search_order")
async def search_order_start(callback: CallbackQuery, state: FSMContext):
    """Start order search; input itself belongs to admin_search_policy."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🔍 <b>بحث عن طلب</b>\n\n"
        "أرسل رقم الطلب الذي يبدأ بـ <code>ORD_</code>.\n"
        "مثال: <code>ORD_20260730_ABC123</code>",
        reply_markup=_cancel_keyboard(),
        parse_mode="HTML",
    )
    await state.update_data(admin_search_type="order")
    await state.set_state(AdminStates.waiting_search)
    await callback.answer()
