"""Authoritative admin pending/active-order listing policy."""
import html
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.admin_order_actions import payment_confirmed_admin_keyboard
from keyboards.inline import admin_menu_keyboard, order_admin_keyboard, order_pagination_keyboard
from services.formatters import money, usdt

logger = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 5
ACTIVE_STATUSES = ("pending", "waiting_payment", "receipt_received", "payment_confirmed")


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _fetch_orders_page(list_type: str, page: int = 0):
    pool = await get_pool()
    statuses = ("pending",) if list_type == "pending" else ACTIVE_STATUSES
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = ANY($1::text[])", list(statuses))
        rows = await conn.fetch(
            "SELECT o.*, u.full_name, u.telegram_id AS user_tg FROM orders o JOIN users u ON o.user_id = u.id "
            "WHERE o.status = ANY($1::text[]) ORDER BY o.created_at DESC LIMIT $2 OFFSET $3",
            list(statuses), PAGE_SIZE, max(0, page) * PAGE_SIZE,
        )
    return rows, total


def _format_order_compact(order, show_detail: bool = False) -> str:
    status_icons = {"pending": "⏳", "waiting_payment": "💳", "receipt_received": "📎", "payment_confirmed": "🚀", "completed": "✅", "rejected": "❌", "expired": "⌛"}
    status_names = {"pending": "قيد الانتظار", "waiting_payment": "بانتظار الدفع", "receipt_received": "تم استلام الإيصال", "payment_confirmed": "تم تأكيد الدفع", "completed": "مكتمل", "rejected": "مرفوض", "expired": "منتهي"}
    icon = status_icons.get(order["status"], "❓")
    name = html.escape(order["full_name"] or "N/A")
    wallet = order["wallet_address"] or ""
    wallet_short = html.escape(wallet[:10] + "..." if len(wallet) > 10 else wallet)
    if show_detail:
        return (
            f"{icon} <b>#{html.escape(order['order_number'])}</b>\n"
            f"👤 {name} | 🆔 <code>{order['user_tg']}</code>\n"
            f"💰 {usdt(order['amount_usdt'])} USDT | 🌐 {html.escape(order['network'] or '')}\n"
            f"💱 {html.escape(order['payment_currency'] or '')} | 💵 {money(order['total_amount'])}\n"
            f"📊 {status_names.get(order['status'], order['status'])}\n"
            f"📍 <code>{wallet_short}</code>\n"
            f"📅 {order['created_at'].strftime('%m-%d %H:%M')}"
        )
    return (
        f"{icon} <b>#{html.escape(order['order_number'])}</b> | 👤 {name}\n"
        f"💰 {usdt(order['amount_usdt'])} USDT | 🌐 {html.escape(order['network'] or '')}\n"
        f"💱 {money(order['total_amount'])} {html.escape(order['payment_currency'] or '')}\n"
        f"📍 <code>{wallet_short}</code>\n"
        f"📅 {order['created_at'].strftime('%m-%d %H:%M')}"
    )


def _order_actions(order_id: int, status: str):
    """Return the canonical admin actions for the current order status."""
    if status == "payment_confirmed":
        return payment_confirmed_admin_keyboard(order_id)
    return order_admin_keyboard(order_id, status)


async def _render_orders(callback: CallbackQuery, list_type: str, page: int):
    rows, total = await _fetch_orders_page(list_type, page)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 0), total_pages - 1)
    if not rows:
        title = "الطلبات المعلقة" if list_type == "pending" else "جميع الطلبات النشطة"
        await callback.message.edit_text(f"✅ لا توجد {title} حالياً", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
        return
    header = f"📦 <b>الطلبات المعلقة</b> ({total}) | صفحة {page + 1}/{total_pages}" if list_type == "pending" else f"📋 <b>جميع الطلبات النشطة</b> ({total}) | صفحة {page + 1}/{total_pages}\n⏳ • 💳 • 📎 • 🚀"
    await callback.message.edit_text(header, parse_mode="HTML")
    for order in rows:
        await callback.message.answer(_format_order_compact(order, show_detail=list_type == "active"), reply_markup=_order_actions(order["id"], order["status"]), parse_mode="HTML")
        if list_type == "active" and order["status"] == "receipt_received" and order.get("receipt_photo_id"):
            try:
                await callback.message.answer_photo(order["receipt_photo_id"], caption=f"📸 إيصال #{order['order_number']}")
            except Exception:
                logger.exception("Failed to send receipt preview for order %s", order["id"])
    await callback.message.answer("⬇️ استخدم الأزرار للتصفح:", reply_markup=order_pagination_keyboard(page, total_pages, list_type), parse_mode="HTML")


@router.callback_query(F.data == "admin_pending_orders")
async def pending_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    await _render_orders(callback, "pending", 0); await callback.answer()


@router.callback_query(F.data.startswith("pending_page_"))
async def pending_orders_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    try: page = int(callback.data.replace("pending_page_", ""))
    except ValueError:
        await callback.answer("❌ صفحة غير صالحة", show_alert=True); return
    await _render_orders(callback, "pending", page); await callback.answer()


@router.callback_query(F.data == "admin_active_orders")
async def active_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    await _render_orders(callback, "active", 0); await callback.answer()


@router.callback_query(F.data.startswith("active_page_"))
async def active_orders_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True); return
    try: page = int(callback.data.replace("active_page_", ""))
    except ValueError:
        await callback.answer("❌ صفحة غير صالحة", show_alert=True); return
    await _render_orders(callback, "active", page); await callback.answer()
