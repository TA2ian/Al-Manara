"""Admin transfer-completion input policy."""
import html
import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from database import get_pool
from services.formatters import usdt
from services.order_completion_service import complete_order
from states import AdminStates

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _valid_txid(txid: str, network: str | None = None) -> bool:
    """Validate transaction hash shape without requiring on-chain verification."""
    value = (txid or "").strip()
    if not value:
        return False
    normalized = (network or "TRC20").upper()
    if normalized == "TRC20":
        return bool(re.fullmatch(r"[0-9a-fA-F]{64}", value))
    if normalized in {"BEP20", "ERC20"}:
        return bool(re.fullmatch(r"0x[0-9a-fA-F]{64}", value))
    return bool(re.fullmatch(r"[0-9A-Za-z_-]{32,128}", value))


@router.callback_query(F.data.startswith("admin_send_usdt_"))
async def admin_send_usdt_start(callback: CallbackQuery, state: FSMContext):
    """Start the direct single-admin USDT transfer completion flow."""
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
            "SELECT order_number, status, network, amount_usdt, wallet_address FROM orders WHERE id = $1",
            order_id,
        )
    if not order:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return
    if order["status"] != "payment_confirmed":
        await callback.answer(f"⚠️ لا يمكن إرسال USDT من الحالة الحالية: {order['status']}", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        admin_txid_order_id=order_id,
        admin_txid_network=order["network"] or "TRC20",
        admin_screenshot_id="",
        admin_fulfillment_admin_id=callback.from_user.id,
    )
    await state.set_state(AdminStates.waiting_typing_txid)
    await callback.message.edit_text(
        f"🚀 <b>إرسال USDT — الطلب #{html.escape(str(order['order_number']))}</b>\n\n"
        f"💰 المبلغ: <b>{usdt(order['amount_usdt'])} USDT</b>\n"
        f"🌐 الشبكة: <b>{html.escape(order['network'] or 'TRC20')}</b>\n"
        f"📍 المحفظة: <code>{html.escape(order['wallet_address'])}</code>\n\n"
        "بعد تنفيذ التحويل الخارجي، أرسل <b>TXID</b> كنص.\n"
        "ويمكنك بدلاً من ذلك إرسال صورة إثبات التحويل، ثم إرسال TXID في رسالة لاحقة.\n\n"
        "⚠️ لا تنفذ التحويل الخارجي أكثر من مرة لهذا الطلب.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_cancel_transfer")]]),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_cancel_transfer")
async def admin_cancel_transfer(callback: CallbackQuery, state: FSMContext):
    """Cancel the current admin transfer input session without changing order state."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("⚙️ <b>تم إلغاء إدخال بيانات التحويل.</b>\n\nلم يتم تغيير حالة الطلب.", parse_mode="HTML")
    await callback.answer("تم الإلغاء")


@router.message(AdminStates.waiting_typing_txid, F.photo)
async def admin_transfer_photo_first(message: Message, state: FSMContext):
    """Accept a proof screenshot before the TXID."""
    data = await state.get_data()
    order_id = data.get("admin_txid_order_id")
    network = data.get("admin_txid_network", "TRC20")
    admin_id = data.get("admin_fulfillment_admin_id")
    if not order_id or not admin_id or int(admin_id) != message.from_user.id:
        await message.answer("❌ لا توجد عملية تحويل صالحة مرتبطة بجلسة الإدارة الحالية.")
        await state.clear()
        return

    screenshot_id = message.photo[-1].file_id
    caption_txid = (message.caption or "").strip()
    if _valid_txid(caption_txid, network):
        await complete_order(message, state, caption_txid, screenshot_id, int(order_id), int(admin_id))
        return

    await state.update_data(admin_screenshot_id=screenshot_id)
    await message.answer(
        f"📸 <b>تم استلام صورة إثبات التحويل للطلب #{html.escape(str(order_id))}.</b>\n\n"
        "🔗 الآن أرسل TXID الصحيح كنص لإكمال الطلب وإرسال الإثبات للعميل.",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_typing_txid, F.text)
async def admin_transfer_txid(message: Message, state: FSMContext):
    """Read and finalize the TXID directly from the single configured admin."""
    data = await state.get_data()
    order_id = data.get("admin_txid_order_id")
    screenshot_id = data.get("admin_screenshot_id", "")
    network = data.get("admin_txid_network", "TRC20")
    admin_id = data.get("admin_fulfillment_admin_id")
    txid = (message.text or "").strip()
    if not order_id or not admin_id or int(admin_id) != message.from_user.id:
        await message.answer("❌ لا توجد عملية تحويل صالحة مرتبطة بجلسة الإدارة الحالية.")
        await state.clear()
        return
    if not _valid_txid(txid, network):
        await message.answer("❌ صيغة TXID غير صحيحة لهذه الشبكة. تحقق من TXID وأرسله مرة أخرى.")
        return
    await complete_order(message, state, txid, screenshot_id, int(order_id), int(admin_id))
