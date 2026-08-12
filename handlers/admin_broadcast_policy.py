"""Authoritative admin broadcast flow with preview, confirmation and cancellation."""
import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from database import get_pool
from states import AdminStates

router = Router()
logger = logging.getLogger(__name__)

MAX_BROADCAST_LENGTH = 4096
BROADCAST_DELAY_SECONDS = 0.05


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 إرسال للجميع", callback_data="admin_broadcast_send")],
        [InlineKeyboardButton(text="✏️ تعديل", callback_data="admin_broadcast_edit"),
         InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_broadcast_cancel")],
        [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
    ])


def broadcast_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_broadcast_cancel")],
        [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
    ])


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast composition without sending anything."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.message.edit_text(
        "📨 <b>إرسال إشعار جماعي</b>\n\n"
        "أرسل الآن نص الرسالة التي تريد إرسالها.\n"
        "لن يتم إرسالها مباشرة؛ ستظهر لك معاينة قبل الإرسال.\n\n"
        "الحد الأقصى: 4096 حرف.",
        parse_mode="HTML",
        reply_markup=broadcast_start_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_broadcast)
async def capture_broadcast(message: Message, state: FSMContext):
    """Capture the draft and require explicit confirmation."""
    if not is_admin(message.from_user.id):
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ أرسل نصاً فعلياً للرسالة.")
        return
    if len(text) > MAX_BROADCAST_LENGTH:
        await message.answer(f"❌ الرسالة طويلة جداً. الحد الأقصى {MAX_BROADCAST_LENGTH} حرف.")
        return

    await state.update_data(broadcast_text=text)
    await state.set_state(AdminStates.waiting_broadcast_preview)

    await message.answer(
        "👁 <b>معاينة الإشعار</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        f"{text}\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚠️ لم يتم الإرسال بعد. اختر إجراءً:",
        parse_mode="HTML",
        reply_markup=broadcast_preview_keyboard(),
    )


@router.callback_query(AdminStates.waiting_broadcast_preview, F.data == "admin_broadcast_edit")
async def edit_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.message.edit_text(
        "✏️ <b>تعديل الإشعار</b>\n\nأرسل النص الجديد.\nلم يتم إرسال أي شيء حتى الآن.",
        parse_mode="HTML",
        reply_markup=broadcast_start_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    from keyboards.inline import admin_menu_keyboard
    await callback.message.edit_text(
        "❌ تم إلغاء الإشعار. لم يتم إرسال أي رسالة.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminStates.waiting_broadcast_preview, F.data == "admin_broadcast_send")
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    """Send the confirmed draft to eligible users and report delivery counts."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await state.clear()
        await callback.answer("❌ لا توجد رسالة جاهزة للإرسال", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT telegram_id FROM users "
            "WHERE terms_accepted = TRUE AND is_blocked = FALSE "
            "ORDER BY id ASC"
        )

    await callback.message.edit_text(
        f"📤 <b>جارٍ إرسال الإشعار...</b>\n\nالمستلمون: {len(users)}\n\n"
        "لا تغلق المحادثة حتى تظهر النتيجة.",
        parse_mode="HTML",
    )
    await callback.answer("📤 بدأ الإرسال")

    sent = 0
    failed = 0
    bot = callback.bot
    for user in users:
        try:
            await bot.send_message(user["telegram_id"], text)
            sent += 1
        except Exception as exc:
            failed += 1
            logger.warning("Broadcast delivery failed for %s: %s", user["telegram_id"], exc)
        await asyncio.sleep(BROADCAST_DELAY_SECONDS)

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO audit_logs (admin_id, action, details, severity) "
            "VALUES ($1, 'broadcast_sent', $2, $3)",
            callback.from_user.id,
            f"recipients={len(users)};sent={sent};failed={failed}",
            "info" if failed == 0 else "warning",
        )

    await state.clear()
    from keyboards.inline import admin_menu_keyboard
    await callback.message.edit_text(
        "✅ <b>اكتمل الإرسال</b>\n\n"
        f"👥 المستهدفون: <b>{len(users)}</b>\n"
        f"📤 تم الإرسال: <b>{sent}</b>\n"
        f"⚠️ فشل: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
