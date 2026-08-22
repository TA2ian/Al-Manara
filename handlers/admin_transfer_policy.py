"""Admin transfer-completion input policy.

Makes the final transfer-proof flow explicit: a screenshot can be submitted
first and the TXID afterward, or a screenshot can carry the TXID in its caption.
The existing completion function remains the single finalization path.
"""
import html

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from database import get_pool
from states import AdminStates

router = Router()


def _valid_txid(txid: str) -> bool:
    return bool(txid and len(txid.strip()) >= 5)


async def _order_for_admin(order_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name FROM orders o "
            "JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )


@router.message(AdminStates.waiting_typing_txid, F.photo)
async def admin_transfer_photo_first(message: Message, state: FSMContext):
    """Accept a proof screenshot even when the admin sends it before the TXID."""
    data = await state.get_data()
    order_id = data.get("admin_txid_order_id")
    if not order_id:
        await message.answer("❌ لا يوجد طلب مرتبط بهذه العملية. ابدأ من زر إرسال USDT.")
        await state.clear()
        return

    screenshot_id = message.photo[-1].file_id
    caption_txid = (message.caption or "").strip()

    if _valid_txid(caption_txid):
        from handlers.admin import complete_order
        await complete_order(message, state, caption_txid, screenshot_id, order_id)
        return

    await state.update_data(admin_screenshot_id=screenshot_id)
    await message.answer(
        f"📸 <b>تم استلام صورة إثبات التحويل للطلب #{html.escape(str(order_id))}.</b>\n\n"
        "🔗 الآن أرسل TXID كنص لإكمال الطلب وإرسال الإثبات للعميل."
    , parse_mode="HTML")
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

    from handlers.admin import complete_order
    await complete_order(message, state, txid, screenshot_id, order_id)
