"""Financial-only admin dashboard policy."""
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard

router = Router()


def _fmt_usdt(value) -> str:
    try:
        return f"{Decimal(str(value)):,.3f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.000"


def _fmt_money(value) -> str:
    try:
        return f"{Decimal(str(value)):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


async def _dashboard(callback: CallbackQuery):
    if callback.from_user.id not in Config.ADMIN_IDS:
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
               GROUP BY status
               ORDER BY status"""
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
        f"{labels.get(row['status'], row['status'])}: <b>{row['count']}</b> — {_fmt_usdt(row['usdt'])} USDT"
        for row in states
    ]
    state_text = "\n".join(state_lines) if state_lines else "لا توجد طلبات نشطة"

    text = (
        "📊 <b>لوحة الأداء المالي</b>\n\n"
        "━━━ اليوم ━━━\n"
        f"📦 الطلبات: <b>{today['orders']}</b>\n"
        f"✅ المكتمل: <b>{today['completed']}</b>\n"
        f"💰 USDT: <b>{_fmt_usdt(today['usdt'])}</b>\n"
        f"💵 الرسوم: <b>{_fmt_money(today['fees'])}</b>\n\n"
        "━━━ آخر 7 أيام ━━━\n"
        f"📦 الطلبات: <b>{week['orders']}</b>\n"
        f"✅ المكتمل: <b>{week['completed']}</b>\n"
        f"💰 USDT: <b>{_fmt_usdt(week['usdt'])}</b>\n"
        f"💵 الرسوم: <b>{_fmt_money(week['fees'])}</b>\n\n"
        "━━━ هذا الشهر ━━━\n"
        f"📦 الطلبات: <b>{month['orders']}</b>\n"
        f"✅ المكتمل: <b>{month['completed']}</b>\n"
        f"💰 USDT: <b>{_fmt_usdt(month['usdt'])}</b>\n"
        f"💵 الرسوم: <b>{_fmt_money(month['fees'])}</b>\n\n"
        "━━━ الطلبات النشطة ━━━\n"
        f"{state_text}\n\n"
        f"⌛ منتهية اليوم: <b>{expired_today}</b>"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 التحليل المالي", callback_data="admin_analytics")],
            [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_dashboard")
async def financial_dashboard(callback: CallbackQuery):
    """Replace the legacy customer-metrics dashboard with financial metrics."""
    await _dashboard(callback)
