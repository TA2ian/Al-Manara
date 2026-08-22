"""Polished admin order-note flow.

This router intentionally runs before the legacy admin note handlers so the
note experience is clear, contextual, and consistent with the rest of the
admin UI. Notes remain internal to the admin order record.
"""
import html
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from database import get_pool
from states import AdminStates

logger = logging.getLogger(__name__)
router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.callback_query(F.data.startswith("admin_note_"))
async def admin_note_start(callback: CallbackQuery, state: FSMContext):
    """Start the polished internal order-note flow."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_note_", ""))
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
    amount = f"{order['amount_usdt']}"
    currency = html.escape(order["payment_currency"] or "USD")

    await state.update_data(admin_note_order_id=order_id)
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
    await state.set_state(AdminStates.waiting_note_text)
    await callback.answer()


@router.message(AdminStates.waiting_note_text)
async def admin_save_note(message: Message, state: FSMContext):
    """Save an internal order note and record it in the audit timeline."""
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        await state.clear()
        return

    note = (message.text or "").strip()
    if not note:
        await message.answer(
            "📝 <b>الملاحظة فارغة</b>\n\n"
            "أرسل نص الملاحظة التي تريد حفظها في سجل الطلب.",
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
            "SELECT order_number FROM orders WHERE id = $1",
            order_id,
        )
        if not order:
            await message.answer("❌ الطلب غير موجود.")
            await state.clear()
            return

        # Keep the existing note history format while also making the note
        # visible in the order audit timeline.
        await conn.execute(
            "UPDATE orders SET admin_notes = CONCAT(COALESCE(admin_notes, ''), $1, '\\n') WHERE id = $2",
            f"[{message.from_user.id}] {note}",
            order_id,
        )
        await conn.execute(
            "INSERT INTO audit_logs (user_id, admin_id, action, details, severity) "
            "SELECT user_id, $1, 'note', $2, 'info' FROM orders WHERE id = $3",
            message.from_user.id,
            f"order={order['order_number']} | {note}",
            order_id,
        )

    await message.answer(
        "✅ <b>تم حفظ الملاحظة</b>\n\n"
        f"📦 الطلب: <b>#{html.escape(order['order_number'])}</b>\n"
        "📝 تمت إضافة الملاحظة إلى سجل الطلب بنجاح.\n\n"
        "🔒 الملاحظة داخلية وتظهر للمشرفين فقط.",
        parse_mode="HTML",
    )
    await state.clear()
