"""Authoritative customer-search input handler."""
import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard
from services.formatters import usdt
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.message(AdminStates.waiting_search, F.text)
async def search_customer(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    data = await state.get_data()
    if data.get("admin_search_type") != "user":
        return

    query = (message.text or "").strip()
    clean = query.lstrip("@").strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        if clean.isdigit():
            rows = await conn.fetch("SELECT * FROM users WHERE telegram_id=$1", int(clean))
        else:
            rows = await conn.fetch(
                """SELECT * FROM users
                   WHERE username ILIKE $1
                      OR full_name ILIKE $1
                      OR phone_number ILIKE $1
                      OR shamcash_account ILIKE $1
                   ORDER BY created_at DESC LIMIT 20""",
                f"%{clean}%",
            )

        result_rows = []
        for user in rows:
            stats = await conn.fetchrow(
                """SELECT COUNT(*) FILTER (WHERE status='completed') AS completed,
                          COUNT(*) FILTER (WHERE status IN ('pending','waiting_payment','receipt_received','payment_confirmed')) AS active,
                          COALESCE(SUM(amount_usdt) FILTER (WHERE status='completed'),0) AS usdt_completed
                   FROM orders WHERE user_id=$1""",
                user["id"],
            )
            result_rows.append((user, stats))

    await state.clear()
    if not result_rows:
        await message.answer("❌ لم يتم العثور على عميل مطابق.", reply_markup=admin_menu_keyboard())
        return

    for user, stats in result_rows:
        text = (
            "👤 <b>معلومات العميل</b>\n\n"
            f"🆔 Telegram ID: <code>{user['telegram_id']}</code>\n"
            f"📛 الاسم: {html.escape(user['full_name'] or 'N/A')}\n"
            f"📱 اليوزر: @{html.escape(user['username'] or 'N/A')}\n"
            f"📞 الهاتف: <code>{html.escape(user['phone_number'] or 'N/A')}</code>\n"
            f"🏦 ShamCash: <code>{html.escape(user['shamcash_account'] or 'N/A')}</code>\n"
            f"🔰 التوثيق: {'✅' if user['is_verified'] else '❌'} — {html.escape(user['verification_status'] or 'N/A')}\n"
            f"🚫 محظور: {'نعم' if user['is_blocked'] else 'لا'}\n"
            f"📦 طلبات مكتملة: <b>{stats['completed']}</b>\n"
            f"⏳ طلبات نشطة: <b>{stats['active']}</b>\n"
            f"💰 USDT مكتمل: <b>{usdt(stats['usdt_completed'])}</b>\n"
            f"📅 التسجيل: {user['created_at'].strftime('%Y-%m-%d')}"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
