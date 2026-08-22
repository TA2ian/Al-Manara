"""Authoritative admin user-management policy.

Owns user listing, ban/unban, and irreversible user deletion.  The legacy
admin router remains loaded for compatibility, but this policy is registered
before it so these flows have one authoritative implementation.
"""
import html
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _fetch_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT telegram_id, full_name, username, language, is_verified, is_blocked, created_at "
            "FROM users WHERE terms_accepted = TRUE AND is_blocked = FALSE "
            "ORDER BY full_name ASC NULLS LAST"
        )


@router.callback_query(F.data == "admin_list_users")
async def admin_list_users(callback: CallbackQuery):
    """List active users with safe pagination."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    users = await _fetch_users()
    if not users:
        await callback.message.edit_text("📭 لا يوجد عملاء مسجلون.", parse_mode="HTML")
        await callback.answer()
        return

    page_size = 15
    total_pages = (len(users) + page_size - 1) // page_size
    await _render_user_page(callback, users, 0, total_pages, page_size)
    await callback.answer()


async def _render_user_page(callback: CallbackQuery, users, page: int, total_pages: int, page_size: int):
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    visible_users = users[start:start + page_size]
    lines = []
    buttons = []

    for i, user in enumerate(visible_users, start + 1):
        name = html.escape(user["full_name"] or "—")
        username = html.escape(user["username"] or "—")
        verified = "✅" if user["is_verified"] else "⏳"
        lang_flag = "🇸🇦" if user["language"] == "ar" else "🇬🇧"
        telegram_id = user["telegram_id"]
        lines.append(
            f"{i}. {verified} <b>{name}</b>\n"
            f"   🆔 <code>{telegram_id}</code> | @{username} | {lang_flag}"
        )
        buttons.append([
            InlineKeyboardButton(text=f"🚫 حظر #{i}", callback_data=f"admin_ban_{telegram_id}"),
            InlineKeyboardButton(text=f"🗑️ حذف #{i}", callback_data=f"admin_del_user_{telegram_id}"),
        ])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"users_page_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="admin_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="التالي ▶️", callback_data=f"users_page_{page + 1}"))
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_menu")])

    text = (
        f"📍 <b>قائمة العملاء</b> ({len(users)})\n"
        "━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("users_page_"))
async def admin_users_page(callback: CallbackQuery):
    """Navigate user-list pages."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    try:
        page = int(callback.data.replace("users_page_", ""))
    except ValueError:
        await callback.answer("❌ صفحة غير صالحة", show_alert=True)
        return

    users = await _fetch_users()
    page_size = 15
    total_pages = max(1, (len(users) + page_size - 1) // page_size)
    await _render_user_page(callback, users, page, total_pages, page_size)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban_"), ~F.data.startswith("admin_ban_confirm_"))
async def admin_ban_user(callback: CallbackQuery):
    """Show a confirmation screen before banning a user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    try:
        telegram_id = int(callback.data.replace("admin_ban_", ""))
    except ValueError:
        await callback.answer("❌ معرف غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT full_name, telegram_id, is_blocked FROM users WHERE telegram_id = $1",
            telegram_id,
        )
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    if user["is_blocked"]:
        await callback.answer("✅ المستخدم محظور بالفعل", show_alert=True)
        return

    await callback.message.edit_text(
        "🚫 <b>تأكيد حظر المستخدم</b>\n\n"
        f"👤 {html.escape(user['full_name'] or 'N/A')}\n"
        f"🆔 <code>{telegram_id}</code>\n\n"
        "هل تريد حظر هذا المستخدم؟\n"
        "لن يتمكن من إنشاء طلبات أو استخدام البوت.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ تأكيد الحظر", callback_data=f"admin_ban_confirm_{telegram_id}"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_menu"),
        ]]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban_confirm_"))
async def admin_ban_user_execute(callback: CallbackQuery):
    """Execute a user ban."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    telegram_id = int(callback.data.replace("admin_ban_confirm_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_blocked = TRUE WHERE telegram_id = $1", telegram_id)
        await conn.execute(
            "INSERT INTO blocked_users (telegram_id, blocked_by) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            telegram_id,
            callback.from_user.id,
        )
    await callback.message.edit_text(
        f"✅ <b>تم حظر المستخدم</b>\n🆔 <code>{telegram_id}</code>",
        parse_mode="HTML",
    )
    await callback.message.answer("⚙️ لوحة التحكم", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unban_"), ~F.data.startswith("admin_unban_confirm_"))
async def admin_unban_user(callback: CallbackQuery):
    """Show a confirmation screen before unbanning a user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    telegram_id = int(callback.data.replace("admin_unban_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT full_name, telegram_id, is_blocked FROM users WHERE telegram_id = $1",
            telegram_id,
        )
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    if not user["is_blocked"]:
        await callback.answer("✅ المستخدم غير محظور", show_alert=True)
        return

    await callback.message.edit_text(
        "✅ <b>تأكيد فك الحظر</b>\n\n"
        f"👤 {html.escape(user['full_name'] or 'N/A')}\n"
        f"🆔 <code>{telegram_id}</code>\n\n"
        "هل تريد فك الحظر عن هذا المستخدم؟",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ تأكيد فك الحظر", callback_data=f"admin_unban_confirm_{telegram_id}"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_menu"),
        ]]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unban_confirm_"))
async def admin_unban_user_execute(callback: CallbackQuery):
    """Execute a user unban."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    telegram_id = int(callback.data.replace("admin_unban_confirm_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_blocked = FALSE WHERE telegram_id = $1", telegram_id)
    await callback.message.edit_text(
        f"✅ <b>تم فك الحظر عن المستخدم</b>\n🆔 <code>{telegram_id}</code>",
        parse_mode="HTML",
    )
    await callback.message.answer("⚙️ لوحة التحكم", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del_user_"))
async def admin_del_user(callback: CallbackQuery):
    """Show irreversible user-deletion confirmation."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    telegram_id = int(callback.data.replace("admin_del_user_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT full_name, telegram_id FROM users WHERE telegram_id = $1",
            telegram_id,
        )
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    await callback.message.edit_text(
        "🗑️ <b>تأكيد حذف المستخدم</b>\n\n"
        f"👤 {html.escape(user['full_name'] or 'N/A')}\n"
        f"🆔 <code>{telegram_id}</code>\n\n"
        "⚠️ <b>تحذير:</b> سيتم حذف جميع بيانات هذا المستخدم نهائياً:\n"
        "• بيانات الحساب\n• جميع الطلبات\n• العناوين المحفوظة\n• سجل الحظر والملاحظات\n\n"
        "🚫 <b>هذا الإجراء لا يمكن التراجع عنه.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🗑️ تأكيد الحذف", callback_data=f"admin_del_confirm_{telegram_id}"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_menu"),
        ]]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del_confirm_"))
async def admin_del_user_execute(callback: CallbackQuery):
    """Delete a user's data transactionally and notify them."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    telegram_id = int(callback.data.replace("admin_del_confirm_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(
                "SELECT id, telegram_id, full_name, language FROM users WHERE telegram_id = $1 FOR UPDATE",
                telegram_id,
            )
            if not user:
                await callback.answer("❌ المستخدم غير موجود", show_alert=True)
                return

            user_id = user["id"]
            lang = user["language"] or "ar"
            order_count = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE user_id = $1", user_id)
            addr_count = await conn.fetchval("SELECT COUNT(*) FROM saved_addresses WHERE user_id = $1", user_id)

            await conn.execute("DELETE FROM orders WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM saved_addresses WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM blocked_users WHERE telegram_id = $1", telegram_id)
            await conn.execute("DELETE FROM feedback_messages WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM audit_logs WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

            # The audit entry intentionally has no user_id because the subject
            # has just been removed; admin_id remains the accountable actor.
            await conn.execute(
                "INSERT INTO audit_logs (user_id, admin_id, action, details, severity) "
                "VALUES (NULL, $1, 'user_deleted', $2, 'warning')",
                callback.from_user.id,
                f"Deleted user {user['full_name'] or 'N/A'} (tg:{telegram_id}). Orders: {order_count}, Addresses: {addr_count}",
            )

    try:
        from aiogram import Bot
        bot = Bot(token=Config.BOT_TOKEN)
        if lang == "ar":
            text = (
                "🗑️ <b>تم حذف حسابك</b>\n\n"
                "تم حذف حسابك وجميع بياناتك من نظامنا.\n\n"
                "إذا كان لديك أي استفسار، يمكنك التواصل مع الدعم."
            )
        else:
            text = (
                "🗑️ <b>Your Account Has Been Deleted</b>\n\n"
                "Your account and all associated data have been deleted from our system.\n\n"
                "If you have any questions, you can contact support."
            )
        await bot.send_message(telegram_id, text, parse_mode="HTML")
    except Exception:
        logger.exception("Failed to notify deleted user %s", telegram_id)

    await callback.message.edit_text(
        "✅ <b>تم حذف المستخدم</b>\n"
        f"🆔 <code>{telegram_id}</code>\n"
        f"📊 تم حذف {order_count} طلب/طلبات\n"
        f"📍 تم حذف {addr_count} عنوان/عناوين محفوظة",
        parse_mode="HTML",
    )
    await callback.message.answer("⚙️ لوحة التحكم", reply_markup=admin_menu_keyboard())
    await callback.answer()
