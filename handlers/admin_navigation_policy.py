"""Authoritative admin navigation and analytics."""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard
from states import AdminStates

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء والعودة للوحة التحكم", callback_data="admin_cancel_input")]
        ]
    )


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

    pool = await get_pool()
    async with pool.acquire() as conn:
        today = await conn.fetchrow(
            """SELECT COUNT(*) AS orders,
                      COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                      COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE created_at >= CURRENT_DATE"""
        )
        week = await conn.fetchrow(
            """SELECT COUNT(*) AS orders,
                      COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                      COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"""
        )
        month = await conn.fetchrow(
            """SELECT COUNT(*) AS orders,
                      COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                      COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"""
        )
        states = await conn.fetch(
            """SELECT status, COUNT(*) AS count, COALESCE(SUM(amount_usdt), 0) AS usdt
               FROM orders
               WHERE status IN ('pending','waiting_payment','receipt_received','payment_confirmed')
               GROUP BY status ORDER BY status"""
        )
        expired_today = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE status = 'expired' AND created_at >= CURRENT_DATE"
        )

    labels = {
        "pending": "⏳ معلقة",
        "waiting_payment": "💳 بانتظار الدفع",
        "receipt_received": "📎 الإيصالات للمراجعة",
        "payment_confirmed": "✅ الدفع مؤكد",
    }
    state_lines = [
        f"{labels.get(row['status'], row['status'])}: <b>{row['count']}</b> — {row['usdt']:,.2f} USDT"
        for row in states
    ]
    state_text = "\n".join(state_lines) if state_lines else "لا توجد طلبات نشطة"

    text = (
        "📊 <b>لوحة الأداء المالي</b>\n\n"
        "━━━ اليوم ━━━\n"
        f"📦 الطلبات: <b>{today['orders']}</b>\n"
        f"✅ المكتمل: <b>{today['completed']}</b>\n"
        f"💰 USDT: <b>{today['usdt']:,.2f}</b>\n"
        f"💵 الرسوم: <b>{today['fees']:,.2f}</b>\n\n"
        "━━━ آخر 7 أيام ━━━\n"
        f"📦 الطلبات: <b>{week['orders']}</b>\n"
        f"✅ المكتمل: <b>{week['completed']}</b>\n"
        f"💰 USDT: <b>{week['usdt']:,.2f}</b>\n"
        f"💵 الرسوم: <b>{week['fees']:,.2f}</b>\n\n"
        "━━━ هذا الشهر ━━━\n"
        f"📦 الطلبات: <b>{month['orders']}</b>\n"
        f"✅ المكتمل: <b>{month['completed']}</b>\n"
        f"💵 الرسوم: <b>{month['fees']:,.2f}</b>\n"
        f"💰 USDT: <b>{month['usdt']:,.2f}</b>\n\n"
        "━━━ الطلبات النشطة ━━━\n"
        f"{state_text}\n\n"
        f"⌛ منتهية اليوم: <b>{expired_today}</b>"
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
    """Show financial/business analytics only."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    await state.clear()
    pool = await get_pool()
    async with pool.acquire() as conn:
        completed = await conn.fetchrow(
            """SELECT COUNT(*) AS count,
                      COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE status = 'completed'"""
        )
        active = await conn.fetchrow(
            """SELECT COUNT(*) AS count,
                      COALESCE(SUM(amount_usdt), 0) AS usdt
               FROM orders
               WHERE status IN ('pending','waiting_payment','receipt_received','payment_confirmed')"""
        )
        today = await conn.fetchrow(
            """SELECT COUNT(*) AS count,
                      COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders
               WHERE created_at >= CURRENT_DATE AND status = 'completed'"""
        )
        currency_rows = await conn.fetch(
            """SELECT payment_currency,
                      COUNT(*) AS count,
                      COALESCE(SUM(total_amount), 0) AS total
               FROM orders
               WHERE status = 'completed'
               GROUP BY payment_currency
               ORDER BY payment_currency"""
        )

    currency_lines = [
        f"• {row['payment_currency']}: {row['count']} طلب — {row['total']:,.2f}"
        for row in currency_rows
    ]
    currency_text = "\n".join(currency_lines) if currency_lines else "• لا توجد بيانات مكتملة بعد"

    text = (
        "📈 <b>التحليل المالي</b>\n\n"
        "━━━ الأداء المالي ━━━\n"
        f"💰 USDT المسلم: <b>{completed['usdt']:,.2f}</b>\n"
        f"💵 رسوم محققة: <b>{completed['fees']:,.2f}</b>\n"
        f"📦 طلبات مكتملة: <b>{completed['count']}</b>\n\n"
        "━━━ اليوم ━━━\n"
        f"📦 مكتمل: <b>{today['count']}</b>\n"
        f"💰 USDT: <b>{today['usdt']:,.2f}</b>\n"
        f"💵 رسوم: <b>{today['fees']:,.2f}</b>\n\n"
        "━━━ قيد التنفيذ ━━━\n"
        f"⏳ الطلبات النشطة: <b>{active['count']}</b>\n"
        f"💰 قيمتها: <b>{active['usdt']:,.2f} USDT</b>\n\n"
        "━━━ حسب عملة الدفع ━━━\n"
        f"{currency_text}"
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
