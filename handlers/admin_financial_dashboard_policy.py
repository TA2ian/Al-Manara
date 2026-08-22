"""Financial-only admin dashboard policy."""
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from database import get_pool
from services.formatters import money, usdt

router = Router()


async def _financial_rows():
    pool = await get_pool()
    async with pool.acquire() as conn:
        completed = await conn.fetchrow(
            """SELECT COUNT(*) AS count, COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE status = 'completed'"""
        )
        active = await conn.fetchrow(
            """SELECT COUNT(*) AS count, COALESCE(SUM(amount_usdt), 0) AS usdt
               FROM orders WHERE status IN ('pending','waiting_payment','receipt_received','payment_confirmed')"""
        )
        today = await conn.fetchrow(
            """SELECT COUNT(*) AS count, COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE created_at >= CURRENT_DATE AND status = 'completed'"""
        )
        currency_rows = await conn.fetch(
            """SELECT payment_currency, COUNT(*) AS count,
                      COALESCE(SUM(total_amount), 0) AS total
               FROM orders WHERE status = 'completed'
               GROUP BY payment_currency ORDER BY payment_currency"""
        )
    return completed, active, today, currency_rows


async def _dashboard(callback: CallbackQuery):
    if callback.from_user.id not in Config.ADMIN_IDS:
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        today = await conn.fetchrow(
            """SELECT COUNT(*) AS orders, COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                      COALESCE(SUM(amount_usdt), 0) AS usdt, COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE created_at >= CURRENT_DATE"""
        )
        week = await conn.fetchrow(
            """SELECT COUNT(*) AS orders, COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                      COALESCE(SUM(amount_usdt), 0) AS usdt, COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"""
        )
        month = await conn.fetchrow(
            """SELECT COUNT(*) AS orders, COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                      COALESCE(SUM(amount_usdt), 0) AS usdt, COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"""
        )
        states = await conn.fetch(
            """SELECT status, COUNT(*) AS count, COALESCE(SUM(amount_usdt), 0) AS usdt
               FROM orders WHERE status IN ('pending','waiting_payment','receipt_received','payment_confirmed')
               GROUP BY status ORDER BY status"""
        )
        expired_today = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'expired' AND created_at >= CURRENT_DATE")

    labels = {
        "pending": "⏳ معلقة",
        "waiting_payment": "💳 بانتظار الدفع",
        "receipt_received": "📎 الإيصالات للمراجعة",
        "payment_confirmed": "✅ الدفع مؤكد",
    }
    state_lines = [f"{labels.get(row['status'], row['status'])}: <b>{row['count']}</b> — {usdt(row['usdt'])} USDT" for row in states]
    state_text = "\n".join(state_lines) if state_lines else "لا توجد طلبات نشطة"

    text = (
        "📊 <b>لوحة الأداء المالي</b>\n\n"
        "━━━ اليوم ━━━\n"
        f"📦 الطلبات: <b>{today['orders']}</b>\n"
        f"✅ المكتمل: <b>{today['completed']}</b>\n"
        f"💰 USDT: <b>{usdt(today['usdt'])}</b>\n"
        f"💵 الرسوم: <b>{money(today['fees'])}</b>\n\n"
        "━━━ آخر 7 أيام ━━━\n"
        f"📦 الطلبات: <b>{week['orders']}</b>\n"
        f"✅ المكتمل: <b>{week['completed']}</b>\n"
        f"💰 USDT: <b>{usdt(week['usdt'])}</b>\n"
        f"💵 الرسوم: <b>{money(week['fees'])}</b>\n\n"
        "━━━ هذا الشهر ━━━\n"
        f"📦 الطلبات: <b>{month['orders']}</b>\n"
        f"✅ المكتمل: <b>{month['completed']}</b>\n"
        f"💵 الرسوم: <b>{money(month['fees'])}</b>\n"
        f"💰 USDT: <b>{usdt(month['usdt'])}</b>\n\n"
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


async def _analytics(callback: CallbackQuery):
    if callback.from_user.id not in Config.ADMIN_IDS:
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    completed, active, today, currency_rows = await _financial_rows()
    currency_lines = [f"• {row['payment_currency']}: {row['count']} طلب — {money(row['total'])}" for row in currency_rows]
    currency_text = "\n".join(currency_lines) if currency_lines else "• لا توجد بيانات مكتملة بعد"
    text = (
        "📈 <b>التحليل المالي</b>\n\n"
        "━━━ الأداء المالي ━━━\n"
        f"💰 USDT المسلم: <b>{usdt(completed['usdt'])}</b>\n"
        f"💵 رسوم محققة: <b>{money(completed['fees'])}</b>\n"
        f"📦 طلبات مكتملة: <b>{completed['count']}</b>\n\n"
        "━━━ اليوم ━━━\n"
        f"📦 مكتمل: <b>{today['count']}</b>\n"
        f"💰 USDT: <b>{usdt(today['usdt'])}</b>\n"
        f"💵 رسوم: <b>{money(today['fees'])}</b>\n\n"
        "━━━ قيد التنفيذ ━━━\n"
        f"⏳ الطلبات النشطة: <b>{active['count']}</b>\n"
        f"💰 قيمتها: <b>{usdt(active['usdt'])} USDT</b>\n\n"
        "━━━ حسب عملة الدفع ━━━\n"
        f"{currency_text}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_dashboard")
async def financial_dashboard(callback: CallbackQuery):
    await _dashboard(callback)


@router.callback_query(F.data == "admin_analytics")
async def financial_analytics(callback: CallbackQuery):
    await _analytics(callback)
