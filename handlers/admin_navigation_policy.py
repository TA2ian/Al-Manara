"""Authoritative admin navigation and analytics.

Search input is owned by ``admin_search_policy`` and exchange-rate input is
owned by ``admin_rate_policy``. Operational settings are owned exclusively by
``admin_settings_policy`` so each callback/FSM flow has one authority.
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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
