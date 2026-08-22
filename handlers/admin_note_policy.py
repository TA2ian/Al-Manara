"""Authoritative admin order-note flow."""
import html
import logging
from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup

from config import Config
from database import get_pool
from services.formatters import usdt
from states import AdminStates

logger = logging.getLogger(__name__)
router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _format_usdt(value) -> str:
    try:
        return usdt(value)
    except (InvalidOperation, TypeError, ValueError):
        return "0.000"


@router.callback_query(F.data.startswith("admin_note_"))
async def admin_note_start(callback: CallbackQuery, state: FSMContext):
    """Start the internal note flow and remember the exact invoice message."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.removeprefix("admin_note_"))
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT order_number, status, amount_usdt, payment_currency "
            "FROM orders WHERE id = $1",
            order_id,
        )
    if not order:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return

    status_names = {
        "pending": "قيد الانتظار",
        "waiting_payment": "بانتظار الدفع",
        "receipt_received": "الإيصال قيد المراجعة",
        "payment_confirmed": "تم تأكيد الدفع",
        "completed": "مكتمل",
        "rejected": "مرفوض",
        "expired": "منتهي",
    }
    status = status_names.get(order["status"], order["status"])
    amount = _format_usdt(order["amount_usdt"])
    currency = html.escape(order["payment_currency"] or "USD")

    base_text = callback.message.text or callback.message.caption or ""
    content_kind = "text" if callback.message.text is not None else "caption"
    await state.update_data(
        admin_note_order_id=order_id,
        admin_note_message_id=callback.message.message_id,
        admin_note_chat_id=callback.message.chat.id,
        admin_note_base_text=base_text,
        admin_note_content_kind=content_kind,
        admin_note_reply_markup=(
            callback.message.reply_markup.model_dump()
            if callback.message.reply_markup else None
        ),
    )
    await state.set_state(AdminStates.waiting_note_text)
    await callback.message.answer(
        "📝 <b>إضافة ملاحظة للطلب</b>\n\n"
        f"📦 الطلب: <b>#{html.escape(order['order_number'])}</b>\n"
        f"💰 المبلغ: <b>{amount} USDT</b>\n"
        f"📊 الحالة: <b>{html.escape(status)}</b>\n\n"
        "اكتب الملاحظة التي تريد حفظها في سجل الطلب.\n"
        "🔒 <i>الملاحظة داخلية وتظهر للمشرفين فقط.</i>\n\n"
        "✏️ أرسل النص الآن:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_note_text)
async def admin_save_note(message: Message, state: FSMContext):
    """Persist the note, audit it, and update the original admin invoice."""
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return

    note = (message.text or "").strip()
    if not note:
        await message.answer(
            "📝 <b>الملاحظة فارغة</b>\n\nأرسل نص الملاحظة.",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    order_id = data.get("admin_note_order_id")
    if not order_id:
        await message.answer("❌ انتهت جلسة إضافة الملاحظة. أعد المحاولة من الطلب.")
        await state.clear()
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT order_number, user_id FROM orders WHERE id = $1",
            order_id,
        )
        if not order:
            await message.answer("❌ الطلب غير موجود.")
            await state.clear()
            return

        await conn.execute(
            "UPDATE orders SET admin_notes = CONCAT(COALESCE(admin_notes, ''), $1, '\\n') WHERE id = $2",
            f"[{message.from_user.id}] {note}",
            order_id,
        )
        await conn.execute(
            "INSERT INTO audit_logs (user_id, admin_id, action, details, severity) "
            "VALUES ($1, $2, 'note', $3, 'info')",
            order["user_id"],
            message.from_user.id,
            f"order={order['order_number']} | {note}",
        )

    base = data.get("admin_note_base_text") or ""
    suffix = f"\n\n📝 <b>ملاحظة إدارية:</b> {html.escape(note)}"
    updated_text = base + suffix
    reply_markup = None
    raw_markup = data.get("admin_note_reply_markup")
    if raw_markup:
        try:
            reply_markup = InlineKeyboardMarkup.model_validate(raw_markup)
        except Exception:
            logger.warning("Could not rebuild note invoice keyboard", exc_info=True)

    try:
        if data.get("admin_note_content_kind") == "caption":
            await message.bot.edit_message_caption(
                chat_id=data["admin_note_chat_id"],
                message_id=data["admin_note_message_id"],
                caption=updated_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        else:
            await message.bot.edit_message_text(
                chat_id=data["admin_note_chat_id"],
                message_id=data["admin_note_message_id"],
                text=updated_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    except Exception:
        logger.exception("Failed to refresh original order invoice after note")
        await message.answer(
            "⚠️ تم حفظ الملاحظة في سجل الطلب، لكن تعذر تحديث الرسالة الأصلية."
        )

    await message.answer(
        "✅ <b>تم حفظ الملاحظة وتحديث الفاتورة.</b>\n\n"
        f"📦 الطلب: <b>#{html.escape(order['order_number'])}</b>\n"
        "🔒 الملاحظة داخلية وتظهر للمشرفين فقط.",
        parse_mode="HTML",
    )
    await state.clear()
