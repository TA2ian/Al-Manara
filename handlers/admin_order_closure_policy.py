"""Admin-only order closure without USDT fulfillment."""
import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from database import get_pool
from keyboards.admin_order_actions import (
    close_without_fulfillment_confirmation_keyboard,
    close_without_fulfillment_keyboard,
)
from keyboards.inline import order_admin_keyboard
from keyboards.reply import compact_reply_keyboard
from services.order_state_service import InvalidOrderTransition, transition_order
from states import AdminStates

logger = logging.getLogger(__name__)
router = Router()
MIN_REASON_LENGTH = 5
MAX_REASON_LENGTH = 1000


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _load_order(conn, order_id: int):
    return await conn.fetchrow(
        """SELECT o.*, u.telegram_id, u.full_name, u.language
           FROM orders o
           JOIN users u ON o.user_id = u.id
           WHERE o.id = $1""",
        order_id,
    )


@router.callback_query(F.data.startswith("admin_close_without_fulfillment_"))
async def request_close_without_fulfillment(callback: CallbackQuery, state: FSMContext):
    """Start the guarded reason-entry flow for a payment-confirmed order."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.removeprefix("admin_close_without_fulfillment_"))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await _load_order(conn, order_id)

    if not order:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return
    if order["status"] != "payment_confirmed":
        await callback.answer("⚠️ الإغلاق دون تنفيذ متاح فقط بعد تأكيد الدفع وقبل إرسال USDT", show_alert=True)
        return

    await state.update_data(admin_close_order_id=order_id, admin_close_reason=None)
    await state.set_state(AdminStates.waiting_close_reason)
    await callback.answer()
    await callback.message.edit_text(
        f"🔒 <b>إغلاق الطلب دون تنفيذ USDT</b>\n\n"
        f"📦 الطلب: <b>#{html.escape(order['order_number'])}</b>\n"
        "⚠️ لن يتم إرسال USDT ولن يُسجل الطلب كمكتمل.\n\n"
        "اكتب سبب الإغلاق يدوياً الآن. يجب أن يكون السبب واضحاً ومحدداً، وسيُحفظ ضمن سجل الطلب.",
        parse_mode="HTML",
        reply_markup=close_without_fulfillment_keyboard(order_id),
    )


@router.callback_query(F.data.startswith("admin_close_reason_"))
async def enter_close_reason_again(callback: CallbackQuery, state: FSMContext):
    """Allow the admin to enter or replace the close reason."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.removeprefix("admin_close_reason_"))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await _load_order(conn, order_id)

    if not order or order["status"] != "payment_confirmed":
        await callback.answer("⚠️ لا يمكن تنفيذ هذا الإجراء من الحالة الحالية", show_alert=True)
        return

    data = await state.get_data()
    await state.update_data(admin_close_order_id=order_id, admin_close_reason=data.get("admin_close_reason"))
    await state.set_state(AdminStates.waiting_close_reason)
    await callback.answer()
    await callback.message.edit_text(
        f"✏️ <b>سبب الإغلاق الإداري للطلب #{html.escape(order['order_number'])}</b>\n\n"
        "اكتب السبب الآن. يجب أن يكون بين 5 و1000 حرف.\n"
        "مثال: طلب تجريبي — لا يوجد تحويل USDT فعلي مطلوب.",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_close_reason)
async def receive_close_reason(message: Message, state: FSMContext):
    """Validate and preview the manually entered closure reason."""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    order_id = data.get("admin_close_order_id")
    if not order_id:
        await state.clear()
        await message.answer("❌ انتهت جلسة الإغلاق الإداري. افتح الطلب من جديد.")
        return

    reason = " ".join((message.text or "").split())
    if len(reason) < MIN_REASON_LENGTH or len(reason) > MAX_REASON_LENGTH:
        await message.answer(
            f"❌ السبب غير صالح. يجب أن يكون بين {MIN_REASON_LENGTH} و{MAX_REASON_LENGTH} حرفاً. أعد المحاولة."
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await _load_order(conn, int(order_id))

    if not order or order["status"] != "payment_confirmed":
        await state.clear()
        await message.answer("⚠️ تغيّرت حالة الطلب. لم يتم تنفيذ الإغلاق.")
        return

    await state.update_data(admin_close_reason=reason)
    await message.answer(
        f"⚠️ <b>تأكيد الإغلاق الإداري</b>\n\n"
        f"📦 الطلب: <b>#{html.escape(order['order_number'])}</b>\n"
        "📌 الحالة الحالية: <b>تم تأكيد الدفع</b>\n"
        "🎯 الحالة بعد الإغلاق: <b>مغلق دون تنفيذ USDT</b>\n\n"
        f"📝 <b>السبب:</b>\n{html.escape(reason)}\n\n"
        "لن يتم إنشاء TXID ولن يُسجل الطلب كمكتمل.",
        parse_mode="HTML",
        reply_markup=close_without_fulfillment_confirmation_keyboard(int(order_id)),
    )


@router.callback_query(F.data.startswith("admin_close_confirm_"))
async def confirm_close_without_fulfillment(callback: CallbackQuery, state: FSMContext):
    """Atomically close only a payment-confirmed order after a required reason."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.removeprefix("admin_close_confirm_"))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    data = await state.get_data()
    reason = " ".join((data.get("admin_close_reason") or "").split())
    if len(reason) < MIN_REASON_LENGTH or len(reason) > MAX_REASON_LENGTH:
        await callback.answer("❌ يجب إدخال سبب صالح قبل التأكيد", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await _load_order(conn, order_id)
            if not order:
                await callback.answer("❌ الطلب غير موجود", show_alert=True)
                return
            if order["status"] != "payment_confirmed":
                await callback.answer("⚠️ تغيّرت حالة الطلب، ولم يتم الإغلاق", show_alert=True)
                return

            try:
                updated = await transition_order(
                    conn,
                    order_id,
                    "closed_without_fulfillment",
                    admin_id=callback.from_user.id,
                    updates={"admin_notes": reason},
                )
            except InvalidOrderTransition:
                await callback.answer("⚠️ لا يمكن إغلاق الطلب من حالته الحالية", show_alert=True)
                return

    await state.clear()
    lang = order["language"] or "ar"
    callback_text = "🔒 تم إغلاق الطلب دون تنفيذ USDT" if lang == "ar" else "🔒 Order closed without USDT fulfillment"
    customer_text = (
        f"🔒 <b>تم إغلاق الطلب إدارياً</b>\n\n"
        f"📦 الطلب: #{html.escape(order['order_number'])}\n"
        "لم يتم تنفيذ تحويل USDT لهذا الطلب."
        if lang == "ar" else
        f"🔒 <b>Order closed administratively</b>\n\n"
        f"📦 Order: #{html.escape(order['order_number'])}\n"
        "No USDT transfer was executed for this order."
    )

    from aiogram import Bot

    bot = Bot(token=Config.BOT_TOKEN)
    try:
        await bot.send_message(
            order["telegram_id"],
            customer_text,
            parse_mode="HTML",
            reply_markup=compact_reply_keyboard(lang),
        )
    except Exception:
        logger.exception("Failed to notify customer after administrative close for order %s", order_id)
    finally:
        try:
            await bot.session.close()
        except Exception:
            logger.exception("Failed to close notification bot session")

    await callback.answer(callback_text)
    await callback.message.edit_text(
        f"🔒 <b>تم إغلاق الطلب #{html.escape(updated['order_number'])} دون تنفيذ USDT</b>\n\n"
        f"📝 <b>السبب:</b>\n{html.escape(reason)}",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("admin_close_back_"))
async def cancel_close_flow(callback: CallbackQuery, state: FSMContext):
    """Leave the closure flow without changing the order."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.removeprefix("admin_close_back_"))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    await state.clear()
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await _load_order(conn, order_id)

    if not order:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return

    await callback.answer("لم يتم إجراء أي تغيير")
    await callback.message.edit_text(
        f"📦 <b>الطلب #{html.escape(order['order_number'])}</b>\n\n"
        f"الحالة الحالية: <b>{html.escape(order['status'])}</b>",
        parse_mode="HTML",
        reply_markup=order_admin_keyboard(order_id, order["status"]),
    )
