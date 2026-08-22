"""Customer receipt-file policy.

ShamCash may prevent screenshots inside its app, so customers can export the
transaction proof and send it to Telegram as a document. Exported proofs are
kept as original Telegram files and sent to admins for manual review.
"""
import html
import logging

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from database import get_pool
from states import ReceiptStates
from services.order_state_service import InvalidOrderTransition, transition_order

logger = logging.getLogger(__name__)
router = Router()


async def _lang(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
    return (row["language"] if row else "ar") or "ar"


async def _load_owned_order(order_id: int, telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT o.*, u.telegram_id AS user_telegram_id, u.full_name,
                      u.shamcash_account, u.language
               FROM orders o JOIN users u ON o.user_id = u.id
               WHERE o.id = $1 AND u.telegram_id = $2""",
            order_id, telegram_id,
        )


@router.callback_query(F.data.startswith("upload_receipt_"))
async def start_exported_receipt_upload(callback: CallbackQuery, state: FSMContext):
    """Start the receipt flow with explicit support for exported ShamCash files."""
    order_id = int(callback.data.replace("upload_receipt_", ""))
    order = await _load_owned_order(order_id, callback.from_user.id)
    lang = await _lang(callback.from_user.id)

    if not order:
        await callback.answer("الطلب غير موجود" if lang == "ar" else "Order not found", show_alert=True)
        return

    if order["status"] != "waiting_payment":
        await callback.answer(
            "لا يمكن رفع إثبات لهذا الطلب حالياً" if lang == "ar" else "This order is not awaiting payment proof",
            show_alert=True,
        )
        return

    await state.update_data(receipt_order_id=order_id)
    prompt = (
        f"📎 <b>إرسال إثبات الدفع — الطلب #{order['order_number']}</b>\n\n"
        "بسبب منع شام كاش التقاط الشاشة داخل التطبيق، يمكنك تصدير/تنزيل إثبات العملية من شام كاش ثم إرساله هنا <b>كملف</b>.\n\n"
        "يمكنك أيضاً إرسال صورة إذا كانت متاحة.\n\n"
        "⚠️ تأكد من أن الملف يُظهر بوضوح تاريخ العملية والمبلغ وبيانات المرسل والمستلم."
        if lang == "ar" else
        f"📎 <b>Payment proof — order #{order['order_number']}</b>\n\n"
        "Because ShamCash may block screenshots inside its app, export/download the transaction proof from ShamCash and send it here <b>as a file</b>.\n\n"
        "You can also send an image if available.\n\n"
        "⚠️ Make sure the file clearly shows the transaction date, amount, sender, and recipient."
    )
    await callback.message.answer(prompt, parse_mode="HTML")
    await state.set_state(ReceiptStates.waiting_receipt)
    await callback.answer()


@router.message(ReceiptStates.waiting_receipt, F.document)
async def handle_exported_receipt_document(message: Message, state: FSMContext):
    """Accept exported ShamCash proof as a Telegram document.

    The original file is retained and routed to admins for review. The order
    transition is atomic and is allowed only from ``waiting_payment`` so a
    duplicate/concurrent upload cannot move an order backwards or overwrite a
    later state.
    """
    data = await state.get_data()
    order_id = data.get("receipt_order_id")
    lang = await _lang(message.from_user.id)

    if not order_id:
        await message.answer(
            "❌ لم يتم العثور على الطلب الحالي. أعد فتح طلبك من «طلباتي»." if lang == "ar"
            else "❌ No active receipt request was found. Open the order again from Orders."
        )
        await state.clear()
        return

    order = await _load_owned_order(order_id, message.from_user.id)
    if not order:
        await message.answer("❌ الطلب غير موجود." if lang == "ar" else "❌ Order not found.")
        await state.clear()
        return

    if order["status"] != "waiting_payment":
        await message.answer(
            "⚠️ لم يعد هذا الطلب بانتظار إثبات الدفع." if lang == "ar"
            else "⚠️ This order is no longer awaiting payment proof."
        )
        await state.clear()
        return

    file_id = message.document.file_id
    file_name = message.document.file_name or "payment_proof"
    mime_type = message.document.mime_type or "application/octet-stream"

    attempt_count = int(order["receipt_upload_count"] or 0) + 1

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            order = await transition_order(
                conn,
                order_id,
                "receipt_received",
                updates={
                    "receipt_photo_id": file_id,
                    "receipt_upload_count": attempt_count,
                },
            )
    except InvalidOrderTransition:
        await message.answer(
            "⚠️ لم يعد هذا الطلب بانتظار إثبات الدفع." if lang == "ar"
            else "⚠️ This order is no longer awaiting payment proof."
        )
        await state.clear()
        return

    processing_text = (
        f"⏳ <b>تم استلام إثبات الدفع</b>\n\n"
        f"📦 الطلب: <b>#{order['order_number']}</b>\n"
        f"📄 الملف: <code>{html.escape(file_name)}</code>\n\n"
        "تم استلام الملف بنجاح. جارٍ إرساله للمراجعة والتحقق.\n"
        "لا تحتاج إلى إعادة الإرسال الآن."
        if lang == "ar" else
        f"⏳ <b>Payment proof received</b>\n\n"
        f"📦 Order: <b>#{order['order_number']}</b>\n"
        f"📄 File: <code>{html.escape(file_name)}</code>\n\n"
        "The file was received successfully and is being sent for review and verification.\n"
        "You do not need to send it again now."
    )
    await message.answer(processing_text, parse_mode="HTML")

    bot = Bot(token=Config.BOT_TOKEN)
    admin_text = (
        "📎 <b>إثبات دفع مُصدّر من شام كاش</b>\n\n"
        f"📦 الطلب: <b>#{order['order_number']}</b>\n"
        f"💰 المبلغ: <b>{order['amount_usdt']:.3f} USDT</b> → {html.escape(order['network'])}\n"
        f"💳 المطلوب: <b>{order['total_amount']:.2f} {html.escape(order['payment_currency'])}</b>\n"
        f"👤 العميل: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🏦 حساب العميل: <code>{html.escape(order['shamcash_account'] or 'N/A')}</code>\n"
        f"📄 الملف: <code>{html.escape(file_name)}</code>\n"
        f"🧾 النوع: <code>{html.escape(mime_type)}</code>\n"
        f"🔢 المحاولة: {attempt_count}\n\n"
        "ℹ️ تم استلام الملف الأصلي من العميل، ويحتاج إلى المراجعة قبل تأكيد الدفع."
    )
    if (order["language"] or "ar") != "ar":
        admin_text = (
            "📎 <b>Exported ShamCash payment proof</b>\n\n"
            f"📦 Order: <b>#{order['order_number']}</b>\n"
            f"💰 Amount: <b>{order['amount_usdt']:.3f} USDT</b> → {html.escape(order['network'])}\n"
            f"💳 Required: <b>{order['total_amount']:.2f} {html.escape(order['payment_currency'])}</b>\n"
            f"👤 Customer: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
            f"🏦 Customer account: <code>{html.escape(order['shamcash_account'] or 'N/A')}</code>\n"
            f"📄 File: <code>{html.escape(file_name)}</code>\n"
            f"🧾 Type: <code>{html.escape(mime_type)}</code>\n"
            f"🔢 Attempt: {attempt_count}\n\n"
            "ℹ️ The original exported file was received from the customer and requires review before payment confirmation."
        )

    from keyboards.inline import order_admin_keyboard
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=order_admin_keyboard(order_id, "receipt_received"),
                parse_mode="HTML",
            )
            await bot.send_document(
                admin_id,
                file_id,
                caption=(
                    f"📄 إثبات الدفع الأصلي — #{order['order_number']}"
                    if (order['language'] or 'ar') == 'ar'
                    else f"📄 Original payment proof — #{order['order_number']}"
                ),
            )
        except Exception as exc:
            logger.error("Failed to forward exported receipt for order %s: %s", order_id, exc)

    await state.clear()
