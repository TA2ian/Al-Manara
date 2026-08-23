"""Safe receipt retry and manual-review callbacks."""
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from services.order_state_service import InvalidOrderTransition, transition_order
from services.receipt_service import notify_admins_receipt
from states import ReceiptStates

logger = logging.getLogger(__name__)
router = Router()
MAX_RECEIPT_ATTEMPTS = 3


async def _owned_order(order_id: int, telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name,
                      u.shamcash_account, u.language, u.username
               FROM orders o JOIN users u ON o.user_id = u.id
               WHERE o.id = $1 AND u.telegram_id = $2""",
            order_id,
            telegram_id,
        )


@router.callback_query(F.data.startswith("retry_receipt_"))
async def retry_receipt(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.removeprefix("retry_receipt_"))
    order = await _owned_order(order_id, callback.from_user.id)
    lang = (order["language"] if order else "ar") or "ar"
    if not order:
        await callback.answer("الطلب غير موجود" if lang == "ar" else "Order not found", show_alert=True)
        return
    if order["status"] != "waiting_payment":
        await callback.answer("لا يمكن رفع إيصال لهذا الطلب حالياً" if lang == "ar" else "This order is not awaiting payment proof", show_alert=True)
        return
    attempts = int(order["receipt_upload_count"] or 0)
    if attempts >= MAX_RECEIPT_ATTEMPTS:
        await callback.answer("لقد استنفدت جميع المحاولات" if lang == "ar" else "All receipt attempts have been exhausted", show_alert=True)
        return

    await state.update_data(receipt_order_id=order_id)
    prompt = (
        f"📎 أرسل صورة جديدة للإيصال للطلب #{order['order_number']}\n"
        f"🔄 المحاولة {attempts + 1}/{MAX_RECEIPT_ATTEMPTS}\n\n"
        "تأكد من وضوح تاريخ العملية وبيانات المرسل والمستلم والمبلغ."
        if lang == "ar" else
        f"📎 Send a new receipt image for order #{order['order_number']}\n"
        f"🔄 Attempt {attempts + 1}/{MAX_RECEIPT_ATTEMPTS}\n\n"
        "Make sure the transaction date, sender, recipient, and amount are clear."
    )
    try:
        await callback.message.delete()
    except Exception:
        logger.debug("Could not delete receipt retry prompt", exc_info=True)
    await callback.message.answer(prompt)
    await state.set_state(ReceiptStates.waiting_receipt)
    await callback.answer()


@router.callback_query(F.data.startswith("manual_review_"))
async def manual_review(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.removeprefix("manual_review_"))
    order = await _owned_order(order_id, callback.from_user.id)
    lang = (order["language"] if order else "ar") or "ar"
    if not order:
        await callback.answer("الطلب غير موجود" if lang == "ar" else "Order not found", show_alert=True)
        return
    if order["status"] != "waiting_payment":
        await callback.answer("لا يمكن إرسال هذا الطلب للمراجعة حالياً" if lang == "ar" else "This order cannot be sent for review now", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await transition_order(
                conn,
                order_id,
                "receipt_received",
                updates={
                    "receipt_photo_id": order["receipt_photo_id"],
                    "receipt_upload_count": order["receipt_upload_count"],
                },
            )
        except InvalidOrderTransition:
            await callback.answer("تغيرت حالة الطلب، افتح طلباتك للتحقق" if lang == "ar" else "The order status changed; open Orders to check it", show_alert=True)
            return

        updated = await conn.fetchrow(
            """SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name,
                      u.shamcash_account, u.language, u.username
               FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1""",
            order_id,
        )

    bot = Bot(token=Config.BOT_TOKEN)
    try:
        await callback.message.answer(
            "👨‍💼 <b>تم إرسال الإيصال للمشرف للمراجعة مباشرة.</b>\n\n"
            f"📦 الطلب: <b>#{order['order_number']}</b>\n"
            "يرجى الانتظار حتى تتم مراجعة الدفع."
            if lang == "ar" else
            "👨‍💼 <b>Your receipt was sent directly to the admin for review.</b>\n\n"
            f"📦 Order: <b>#{order['order_number']}</b>\n"
            "Please wait while the payment is reviewed.",
            parse_mode="HTML",
        )
        await notify_admins_receipt(
            bot=bot,
            order=dict(updated),
            photo_id=order["receipt_photo_id"] or "",
            verification_result=None,
            username=order["username"] or callback.from_user.username or "",
            is_auto_verified=False,
        )
    except Exception:
        logger.exception("Failed to forward manual receipt review for order %s", order_id)
    finally:
        await bot.session.close()
        await state.clear()
    await callback.answer()
