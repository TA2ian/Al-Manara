"""Authoritative admin search input handler for customers and orders."""
import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from database import get_pool
from keyboards.admin_messaging import personal_message_keyboard
from keyboards.inline import admin_menu_keyboard
from services.formatters import money, rate, usdt
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.message(AdminStates.waiting_search, F.text)
async def search_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return

    data = await state.get_data()
    search_type = data.get("admin_search_type", "user")
    query = (message.text or "").strip()
    if not query:
        await message.answer("❌ أرسل قيمة للبحث.")
        return

    pool = await get_pool()

    if search_type == "order":
        order_number = query.upper()
        if not order_number.startswith("ORD_"):
            await state.clear()
            await message.answer("❌ صيغة رقم الطلب غير صحيحة. يجب أن يبدأ بـ <code>ORD_</code>.", reply_markup=admin_menu_keyboard(), parse_mode="HTML")
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT o.*, u.full_name, u.telegram_id
                   FROM orders o JOIN users u ON o.user_id = u.id
                   WHERE o.order_number ILIKE $1""",
                order_number,
            )
        await state.clear()
        if not row:
            await message.answer("❌ لم يتم العثور على طلب بهذا الرقم.", reply_markup=admin_menu_keyboard())
            return
        text = (
            f"📦 <b>الطلب #{html.escape(row['order_number'])}</b>\n\n"
            f"👤 العميل: {html.escape(row['full_name'] or 'N/A')}\n"
            f"🆔 <code>{row['telegram_id']}</code>\n"
            f"💰 الكمية: {usdt(row['amount_usdt'])} USDT\n"
            f"🌐 الشبكة: {html.escape(row['network'] or '')}\n"
            f"📊 الحالة: <b>{html.escape(row['status'])}</b>\n"
            f"💱 السعر: <b>{rate(row['exchange_rate'])}</b> {html.escape(row['payment_currency'])}\n"
            f"💵 الإجمالي: <b>{money(row['total_amount'])}</b> {html.escape(row['payment_currency'])}\n"
            f"📅 الإنشاء: {row['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())
        return

    clean = query.lstrip("@").strip()
    pattern = f"%{clean}%"
    async with pool.acquire() as conn:
        if clean.isdigit():
            rows = await conn.fetch(
                """SELECT * FROM users
                   WHERE telegram_id = $1
                      OR phone_number ILIKE $2
                      OR shamcash_account ILIKE $2
                   ORDER BY created_at DESC LIMIT 20""",
                int(clean), pattern,
            )
        else:
            rows = await conn.fetch(
                """SELECT * FROM users
                   WHERE username ILIKE $1
                      OR full_name ILIKE $1
                      OR phone_number ILIKE $1
                      OR shamcash_account ILIKE $1
                   ORDER BY created_at DESC LIMIT 20""",
                pattern,
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

    if len(result_rows) > 1:
        await message.answer(
            f"🔎 تم العثور على <b>{len(result_rows)}</b> عملاء مطابقين.\n\n"
            "لإدارة أو مراسلة عميل، اجعل البحث أكثر تحديداً باستخدام Telegram ID أو @username أو الهاتف أو حساب ShamCash.",
            parse_mode="HTML", reply_markup=admin_menu_keyboard(),
        )
        for user, _stats in result_rows[:10]:
            await message.answer(
                f"👤 <b>{html.escape(user['full_name'] or 'N/A')}</b> — <code>{user['telegram_id']}</code> — @{html.escape(user['username'] or 'N/A')}",
                parse_mode="HTML",
            )
        return

    user, stats = result_rows[0]
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
    await message.answer(text, parse_mode="HTML", reply_markup=personal_message_keyboard(user["telegram_id"], user["is_blocked"]))
