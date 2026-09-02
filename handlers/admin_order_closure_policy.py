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
from services.order_fulfillment_claim import get_fulfillment_claim
from services.order_state_service import InvalidOrderTransition, transition_order
from states import AdminStates

logger = logging.getLogger(__name__)
router = Router()
MIN_REASON_LENGTH = 5
MAX_REASON_LENGTH = 1000


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _load_order(conn, order_id: int, *, for_update: bool = False):
    lock_clause = " FOR UPDATE" if for_update else ""
    return await conn.fetchrow(
        f"""SELECT o.*, u.telegram_id, u.full_name, u.language
           FROM orders o
           JOIN users u ON o.user_id = u.id
           WHERE o.id = $1{lock_clause}""",
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

    active_order_id = (await state.get_data()).get("admin_close_order_id")
    if active_order_id is not None and int(active_order_id) != order_id:
        await callback.answer(
            "⚠️ توجد جلسة إغلاق نشطة لطلب آخر. أكملها أو ألغها أولاً.",
            show_alert=True,
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await _load_order(conn, order_id)
        claim = await get_fulfillment_claim(conn, order_id)

    if not order:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return
    if order["status"] != "payment_confirmed":
        await callback.answer("⚠️ الإغلاق دون تنفيذ متاح فقط بعد تأكيد الدفع وقبل إرسال USDT", show_alert=True)
        return
    if claim:
        await callback.answer(
            "⚠️ لا يمكن إغلاق الطلب الآن؛ توجد جلسة تنفيذ خارجية محجوزة لهذا الطلب.",
            show_alert=True,
        )
        return

    await state.update_data(
        admin_close_order_id=order_id,
        admin_close_admin_id=callback.from_user.id,
        admin_close_reason=None,
    )
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

    data = await state.get_data()
    previous_order_id = data.get("admin_close_order_id")
    if previous_order_id is not None and int(previous_order_id) != order_id:
        await callback.answer(
            "⚠️ توجد جلسة إغلاق نشطة لطلب آخر. أكملها أو ألغها أولاً.",
            show_alert=True,
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await _load_order(conn, order_id)
        claim = await get_fulfillment_claim(conn, order_id)

    if not order or order["status"] != "payment_confirmed":
        await callback.answer("⚠️ لا يمكن تنفيذ هذا الإجراء من الحالة الحالية", show_alert=True)
        return
    if claim:
        await callback.answer("⚠️ توجد جلسة تنفيذ خارجية محجوزة لهذا الطلب", show_alert=True)
        return

    previous_reason = data.get("admin_close_reason") if previous_order_id is not None else None
    await state.update_data(
        admin_close_order_id=order_id,
        admin_close_admin_id=callback.from_user.id,
        admin_close_reason=previous_reason,
    )
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
    admin_id = data.get("admin_close_admin_id")
    if not order_id or admin_id is None or int(admin_id) != message.from_user.id:
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
        claim = await get_fulfillment_claim(conn, int(order_id))

    if not order or order["status"] != "payment_confirmed":
        await state.clear()
        await message.answer("⚠️ تغيّرت حالة الطلب. لم يتم تنفيذ الإغلاق.")
        return
    if claim:
        await state.clear()
        await message.answer("⚠️ بدأ تنفيذ خارجي لهذا الطلب. لم يتم تنفيذ الإغلاق الإداري.")
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
    pending_order_id = data.get("admin_close_order_id")
    pending_admin_id = data.get("admin_close_admin_id")
    try:
        pending_order_id = int(pending_order_id)
        pending_admin_id = int(pending_admin_id)
    except (TypeError, ValueError):
        await callback.answer("❌ جلسة الإغلاق غير صالحة. افتح الطلب من جديد.", show_alert=True)
        await state.clear()
        return
    if pending_admin_id != callback.from_user.id or pending_order_id != order_id:
        await callback.answer("⚠️ جلسة الإغلاق لا تطابق الطلب المحدد، ولم يتم تنفيذ أي تغيير", show_alert=True)
        return

    reason = " ".join((data.get("admin_close_reason") or "").split())
    if len(reason) < MIN_REASON_LENGTH or len(reason) > MAX_REASON_LENGTH:
        await callback.answer("❌ يجب إدخال سبب صالح قبل التأكيد", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await _load_order(conn, order_id, for_update=True)
            if not order:
                await callback.answer("❌ الطلب غير موجود", show_alert=True)
                return
            if order["status"] != "payment_confirmed":
                await callback.answer("⚠️ تغيّرت حالة الطلب، ولم يتم الإغلاق", show_alert=True)
                return

            claim = await get_fulfillment_claim(conn, order_id)
            if claim:
                await callback.answer(
                    "⚠️ بدأ تنفيذ خارجي لهذا الطلب. تم منع الإغلاق الإداري.",
                    show_alert=True,
                )
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

    try:
        await callback.bot.send_message(
            order["telegram_id"],
            customer_text,
            parse_mode="HTML",
            reply_markup=compact_reply_keyboard(lang),
        )
    except Exception:
        logger.exception("Failed to notify customer after administrative close for order %s", order_id)

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

    active_order_id = (await state.get_data()).get("admin_close_order_id")
    if active_order_id is not None and int(active_order_id) != order_id:
        await callback.answer("⚠️ زر الإلغاء لا يطابق جلسة الإغلاق الحالية.", show_alert=True)
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
        reply_markup=(
            __import__("keyboards.admin_order_actions", fromlist=["payment_confirmed_admin_keyboard"]).payment_confirmed_admin_keyboard(order_id)
            if order["status"] == "payment_confirmed"
            else order_admin_keyboard(order_id, order["status"])
        ),
    )
