"""Active-order customer guidance policy."""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database import get_pool
from keyboards.reply import compact_reply_keyboard
from services.formatters import usdt

router = Router()

ACTIVE_STATUSES = (
    "pending",
    "waiting_payment",
    "receipt_received",
    "payment_confirmed",
)


@router.message(F.text.in_(["💰 جديد", "💰 New", "💰 إنشاء طلب شراء", "💰 Buy Order"]))
async def guide_active_order(message: Message, state: FSMContext):
    """Guide active customers; otherwise delegate to the normal order flow."""
    from handlers.order import start_order

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language, terms_accepted, is_blocked, is_verified FROM users WHERE telegram_id = $1",
            message.from_user.id,
        )
        if not user or not user["terms_accepted"] or user["is_blocked"] or not user["is_verified"]:
            await start_order(message, state)
            return
        active_order = await conn.fetchrow(
            "SELECT order_number, created_at, amount_usdt, status FROM orders "
            "WHERE user_id = $1 AND status = ANY($2) ORDER BY created_at DESC LIMIT 1",
            user["id"], ACTIVE_STATUSES,
        )

    if not active_order:
        await start_order(message, state)
        return

    lang = user["language"] or "ar"
    amount_usdt = usdt(active_order["amount_usdt"])
    if lang == "ar":
        status_map = {
            "pending": "بانتظار موافقة الإدارة",
            "waiting_payment": "بانتظار دفع المبلغ ورفع الإيصال",
            "receipt_received": "تم استلام الإيصال — بانتظار مراجعة الإدارة",
            "payment_confirmed": "تم تأكيد الدفع — بانتظار إرسال USDT من الإدارة",
        }
        text = (
            "⚠️ <b>لديك طلب نشط بالفعل</b>\n\n"
            f"📦 الطلب: <b>#{active_order['order_number']}</b>\n"
            f"💰 المبلغ: <b>{amount_usdt} USDT</b>\n"
            f"📊 الحالة الحالية: <b>{status_map.get(active_order['status'], active_order['status'])}</b>\n\n"
            "📋 لمتابعة الطلب، افتح <b>📋 طلباتي</b> من القائمة السفلية.\n"
            "هناك لا تحتاج إلى إجراء آخر الآن؛ سيظهر تقدم الطلب حسب آخر إجراء من الإدارة.\n\n"
            "لا يمكنك إنشاء طلب شراء جديد حتى يكتمل الطلب الحالي."
        )
    else:
        status_map = {
            "pending": "Awaiting admin approval",
            "waiting_payment": "Awaiting payment and receipt upload",
            "receipt_received": "Receipt received — awaiting admin review",
            "payment_confirmed": "Payment confirmed — awaiting USDT transfer by admin",
        }
        text = (
            "⚠️ <b>You already have an active order</b>\n\n"
            f"📦 Order: <b>#{active_order['order_number']}</b>\n"
            f"💰 Amount: <b>{amount_usdt} USDT</b>\n"
            f"📊 Current status: <b>{status_map.get(active_order['status'], active_order['status'])}</b>\n\n"
            "📋 To follow it, open <b>📋 Orders</b> from the bottom menu.\n"
            "You do not need to take another action now; the order progress is updated by the admin.\n\n"
            "You cannot create another order until the current one is completed."
        )

    await message.answer(text, parse_mode="HTML", reply_markup=compact_reply_keyboard(lang))
