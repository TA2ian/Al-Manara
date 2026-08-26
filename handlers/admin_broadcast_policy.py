"""Authoritative admin messaging flows with fixed branded templates."""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from database import get_pool
from keyboards.admin_messaging import message_template_keyboard, personal_message_preview_keyboard
from keyboards.inline import admin_menu_keyboard
from services.admin_message_service import TEMPLATES, render_template
from states import AdminStates

router = Router()
logger = logging.getLogger(__name__)

MAX_BROADCAST_LENGTH = 3500
BROADCAST_DELAY_SECONDS = 0.05


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def broadcast_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_broadcast_cancel")],
        [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
    ])


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 إرسال للجميع", callback_data="admin_broadcast_send")],
        [InlineKeyboardButton(text="✏️ تعديل", callback_data="admin_broadcast_edit"), InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_broadcast_cancel")],
        [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
    ])


def _template_key_from_callback(data: str, prefix: str) -> str | None:
    marker = f"{prefix}_template_"
    if not data.startswith(marker):
        return None
    key = data[len(marker):]
    return key if key in TEMPLATES else None


async def _show_admin_menu(callback: CallbackQuery, state: FSMContext, notice: str | None = None):
    await state.clear()
    await callback.message.edit_text(notice or "⚙️ <b>لوحة التحكم</b>", parse_mode="HTML", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.message.edit_text(
        "📨 <b>إشعار جماعي للمنارة</b>\n\n"
        "اختر نوع الرسالة أولاً. سيتم إرسالها بقالب رسمي ثابت باسم المنارة، ثم ستراجع المعاينة قبل الإرسال.\n\n"
        "لن يتم إرسال أي رسالة من الضغطة الأولى.",
        parse_mode="HTML", reply_markup=message_template_keyboard("admin_broadcast")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_broadcast_template_"))
async def choose_broadcast_template(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    key = _template_key_from_callback(callback.data, "admin_broadcast")
    if key is None:
        await callback.answer("❌ قالب غير صالح", show_alert=True)
        return
    await state.update_data(message_template=key)
    await state.set_state(AdminStates.waiting_broadcast_preview)
    await callback.message.edit_text(
        f"✍️ <b>{TEMPLATES[key].title_ar}</b>\n\nأرسل الآن محتوى الرسالة فقط. سيُضاف تلقائياً إلى القالب الرسمي.\nالحد الأقصى للمحتوى: 3500 حرف.",
        parse_mode="HTML", reply_markup=broadcast_start_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.waiting_broadcast_preview)
async def capture_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    body = (message.text or "").strip()
    if not body:
        await message.answer("❌ أرسل محتوى الرسالة أولاً.")
        return
    if len(body) > MAX_BROADCAST_LENGTH:
        await message.answer(f"❌ المحتوى طويل جداً. الحد الأقصى {MAX_BROADCAST_LENGTH} حرف.")
        return
    data = await state.get_data()
    key = data.get("message_template")
    if key not in TEMPLATES:
        await state.clear()
        await message.answer("❌ انتهت جلسة إنشاء الرسالة. ابدأ الإشعار من جديد.", reply_markup=admin_menu_keyboard())
        return
    preview = render_template(key, body, "ar")
    await state.update_data(message_body=body)
    await state.set_state(AdminStates.waiting_broadcast)
    await message.answer("👁️ <b>المعاينة النهائية</b>\n\n" + preview + "\n\n⚠️ لن يتم الإرسال حتى تضغط «إرسال للجميع».", parse_mode="HTML", reply_markup=broadcast_preview_keyboard())


@router.callback_query(F.data == "admin_broadcast_edit")
async def edit_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    data = await state.get_data()
    key = data.get("message_template")
    if key not in TEMPLATES:
        await _show_admin_menu(callback, state, "❌ انتهت جلسة الرسالة.")
        return
    await state.set_state(AdminStates.waiting_broadcast_preview)
    await callback.message.edit_text(f"✏️ <b>تعديل {TEMPLATES[key].title_ar}</b>\n\nأرسل المحتوى الجديد.", parse_mode="HTML", reply_markup=broadcast_start_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_admin_menu(callback, state, "❌ <b>تم إلغاء الرسالة.</b>")


@router.callback_query(F.data == "admin_broadcast_send")
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    data = await state.get_data()
    key = data.get("message_template")
    body = (data.get("message_body") or "").strip()
    if key not in TEMPLATES or not body:
        await _show_admin_menu(callback, state, "❌ لا توجد مسودة صالحة للإرسال.")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT telegram_id, language, full_name FROM users WHERE terms_accepted = TRUE AND is_blocked = FALSE")
    bot = callback.message.bot
    sent = failed = 0
    for user in users:
        try:
            lang = user["language"] if user["language"] in ("ar", "en") else "ar"
            await bot.send_message(user["telegram_id"], render_template(key, body, lang, recipient_name=user["full_name"]), parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
            logger.exception("Broadcast delivery failed for telegram_id=%s", user["telegram_id"])
        await asyncio.sleep(BROADCAST_DELAY_SECONDS)
    await _show_admin_menu(callback, state, f"📨 <b>اكتمل الإرسال</b>\n\n✅ تم الإرسال: <b>{sent}</b>\n❌ فشل: <b>{failed}</b>\n📊 الإجمالي: <b>{len(users)}</b>")


@router.callback_query(lambda c: c.data and c.data.startswith("admin_personal_message_") and c.data.removeprefix("admin_personal_message_").isdigit())
async def start_personal_message(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    telegram_id = int(callback.data.removeprefix("admin_personal_message_"))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT telegram_id, full_name, is_blocked FROM users WHERE telegram_id = $1", telegram_id)
    if not user or user["is_blocked"]:
        await callback.answer("❌ لا يمكن إرسال رسالة لهذا الحساب حالياً.", show_alert=True)
        return
    await state.clear()
    await state.update_data(personal_telegram_id=telegram_id, personal_name=user["full_name"] or "")
    await state.set_state(AdminStates.waiting_personal_message)
    await callback.message.edit_text(
        f"✉️ <b>رسالة خاصة للعميل</b>\n\n👤 {user['full_name'] or 'بدون اسم'}\n🆔 <code>{telegram_id}</code>\n\nاختر قالب الرسالة. لن تظهر الرسالة إلا لهذا العميل.",
        parse_mode="HTML", reply_markup=message_template_keyboard("admin_personal")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_personal_template_"))
async def choose_personal_template(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    key = _template_key_from_callback(callback.data, "admin_personal")
    if key is None:
        await callback.answer("❌ قالب غير صالح", show_alert=True)
        return
    await state.update_data(message_template=key)
    await state.set_state(AdminStates.waiting_personal_message)
    await callback.message.edit_text(f"✍️ <b>{TEMPLATES[key].title_ar}</b>\n\nأرسل محتوى الرسالة فقط. سيتم وضعه داخل القالب الرسمي.", parse_mode="HTML", reply_markup=broadcast_start_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_personal_message)
async def capture_personal_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    body = (message.text or "").strip()
    data = await state.get_data()
    key = data.get("message_template")
    telegram_id = data.get("personal_telegram_id")
    if not body:
        await message.answer("❌ أرسل محتوى الرسالة أولاً.")
        return
    if key not in TEMPLATES or not telegram_id:
        await state.clear()
        await message.answer("❌ انتهت جلسة الرسالة. ابدأ من ملف العميل مرة أخرى.", reply_markup=admin_menu_keyboard())
        return
    preview = render_template(key, body, "ar", recipient_name=data.get("personal_name"))
    await state.update_data(message_body=body)
    await state.set_state(AdminStates.waiting_personal_message_preview)
    await message.answer("👁️ <b>معاينة الرسالة الخاصة</b>\n\n" + preview + "\n\n⚠️ سيتم إرسالها لهذا العميل فقط.", parse_mode="HTML", reply_markup=personal_message_preview_keyboard())


@router.callback_query(F.data == "admin_personal_message_edit")
async def edit_personal_message(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_personal_message)
    await callback.message.edit_text("✏️ أرسل محتوى الرسالة الخاصة الجديد.", reply_markup=broadcast_start_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_personal_message_cancel")
async def cancel_personal_message(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_admin_menu(callback, state, "❌ <b>تم إلغاء الرسالة الخاصة.</b>")


@router.callback_query(F.data == "admin_personal_message_send")
async def send_personal_message(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    data = await state.get_data()
    telegram_id = data.get("personal_telegram_id")
    key = data.get("message_template")
    body = (data.get("message_body") or "").strip()
    if not telegram_id or key not in TEMPLATES or not body:
        await _show_admin_menu(callback, state, "❌ لا توجد مسودة صالحة للإرسال.")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT telegram_id, full_name, language, is_blocked FROM users WHERE telegram_id = $1", telegram_id)
    if not user or user["is_blocked"]:
        await _show_admin_menu(callback, state, "❌ لم يعد بالإمكان إرسال الرسالة لهذا العميل.")
        return
    lang = user["language"] if user["language"] in ("ar", "en") else "ar"
    text = render_template(key, body, lang, recipient_name=user["full_name"])
    try:
        await callback.message.bot.send_message(telegram_id, text, parse_mode="HTML")
    except Exception:
        logger.exception("Personal message delivery failed for telegram_id=%s", telegram_id)
        await _show_admin_menu(callback, state, "❌ تعذر إرسال الرسالة للعميل.")
        return
    await _show_admin_menu(callback, state, "✉️ <b>تم إرسال الرسالة الخاصة للعميل فقط.</b>")
