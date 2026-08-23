"""Authoritative admin broadcast flow with preview, confirmation and cancellation."""
import asyncio
import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard
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


async def _show_admin_menu(callback: CallbackQuery, state: FSMContext, notice: str | None = None):
    """Return to the admin menu and always terminate the broadcast FSM."""
    await state.clear()
    await callback.message.edit_text(
        notice or "⚙️ <b>لوحة التحكم</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


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
        await message.answer("❌ أرسل نص الإشعار أولاً.")
        return
    if len(text) > MAX_BROADCAST_LENGTH:
        await message.answer(f"❌ الرسالة طويلة جداً. الحد الأقصى {MAX_BROADCAST_LENGTH} حرف.")
        return

    await state.update_data(broadcast_text=text)
    await state.set_state(AdminStates.waiting_broadcast_confirm)
    preview = (
        "👁️ <b>معاينة الإشعار الجماعي</b>\n\n"
        f"{html.escape(text)}\n\n"
        "⚠️ لن يتم الإرسال حتى تضغط «إرسال للجميع»."
    )
    await message.answer(preview, parse_mode="HTML", reply_markup=broadcast_preview_keyboard())


@router.callback_query(F.data == "admin_broadcast_edit")
async def edit_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.message.edit_text(
        "✏️ <b>تعديل الإشعار</b>\n\nأرسل النص الجديد.",
        parse_mode="HTML",
        reply_markup=broadcast_start_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_admin_menu(callback, state, "❌ <b>تم إلغاء الإشعار الجماعي.</b>")


@router.callback_query(F.data == "admin_broadcast_send")
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    data = await state.get_data()
    text = (data.get("broadcast_text") or "").strip()
    if not text:
        await _show_admin_menu(callback, state, "❌ لم توجد مسودة صالحة للإرسال.")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT telegram_id FROM users WHERE terms_accepted = TRUE AND is_blocked = FALSE"
        )

    bot = callback.message.bot
    sent = failed = 0
    for user in users:
        try:
            await bot.send_message(user["telegram_id"], text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(BROADCAST_DELAY_SECONDS)

    await _show_admin_menu(
        callback,
        state,
        f"📨 <b>اكتمل الإرسال الجماعي</b>\n\n✅ تم الإرسال: <b>{sent}</b>\n❌ فشل: <b>{failed}</b>\n📊 الإجمالي: <b>{len(users)}</b>",
    )
