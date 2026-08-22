"""Admin transfer-completion input policy."""
import html

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from database import get_pool
from states import AdminStates
from services.order_completion_service import complete_order

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _valid_txid(txid: str) -> bool:
    return bool(txid and len(txid.strip()) >= 5)


@router.callback_query(F.data.startswith("admin_send_usdt_"))
async def admin_send_usdt_start(callback: CallbackQuery, state: FSMContext):
    """Start the final fulfillment input flow for a payment-confirmed order."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.removeprefix("admin_send_usdt_"))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT order_number, status, network, amount_usdt, wallet_address "
            "FROM orders WHERE id = $1",
            order_id,
        )

    if not order:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return
    if order["status"] != "payment_confirmed":
        await callback.answer(
            f"⚠️ لا يمكن إرسال USDT من الحالة الحالية: {order['status']}",
            show_alert=True,
        )
        return

    await state.clear()
    await state.update_data(admin_txid_order_id=order_id, admin_screenshot_id="")
    await state.set_state(AdminStates.waiting_typing_txid)

    await callback.message.edit_text(
        f"🚀 <b>إرسال USDT — الطلب #{html.escape(order['order_number'])}</b>\n\n"
        f"💰 المبلغ: <b>{order['amount_usdt']} USDT</b>\n"
        f"🌐 الشبكة: <b>{html.escape(order['network'])}</b>\n"
        f"📍 المحفظة: <code>{html.escape(order['wallet_address'])}</code>\n\n"
        "بعد تنفيذ التحويل، أرسل <b>TXID</b> كنص.\n"
        "ويمكنك بدلاً من ذلك إرسال صورة إثبات التحويل، ثم إرسال TXID في رسالة لاحقة.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_cancel_transfer")]
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_cancel_transfer")
async def admin_cancel_transfer(callback: CallbackQuery, state: FSMContext):
    """Cancel the transfer-input FSM without changing the order state."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>تم إلغاء إدخال التحويل.</b>\n\n"
        "لم يتم تغيير حالة الطلب.",
        parse_mode="HTML",
    )
    await callback.answer("تم الإلغاء")


@router.message(AdminStates.waiting_typing_txid, F.photo)
async def admin_transfer_photo_first(message: Message, state: FSMContext):
    """Accept a proof screenshot before the TXID."""
    data = await state.get_data()
    order_id = data.get("admin_txid_order_id")
    if not order_id:
        await message.answer("❌ لا يوجد طلب مرتبط بهذه العملية. ابدأ من زر إرسال USDT.")
        await state.clear()
        return

    screenshot_id = message.photo[-1].file_id
    caption_txid = (message.caption or "").strip()

    if _valid_txid(caption_txid):
        await complete_order(message, state, caption_txid, screenshot_id, order_id)
        return

    await state.update_data(admin_screenshot_id=screenshot_id)
    await message.answer(
        f"📸 <b>تم استلام صورة إثبات التحويل للطلب #{html.escape(str(order_id))}.</b>\n\n"
        "🔗 الآن أرسل TXID كنص لإكمال الطلب وإرسال الإثبات للعميل.",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_typing_txid)


@router.message(AdminStates.waiting_typing_txid, F.text)
async def admin_transfer_txid_after_photo(message: Message, state: FSMContext):
    """Complete the order when TXID arrives after a screenshot."""
    data = await state.get_data()
    order_id = data.get("admin_txid_order_id")
    screenshot_id = data.get("admin_screenshot_id", "")
    txid = (message.text or "").strip()

    if not order_id:
        await message.answer("❌ لا يوجد طلب مرتبط بهذه العملية. ابدأ من زر إرسال USDT.")
        await state.clear()
        return

    if not _valid_txid(txid):
        await message.answer("❌ TXID غير صالح. أرسل TXID صحيحاً (5 أحرف على الأقل).")
        return

    await complete_order(message, state, txid, screenshot_id, order_id)
