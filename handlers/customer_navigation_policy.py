"""Authoritative customer navigation policy for legacy menu callbacks."""
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import currency_selection_keyboard, main_menu_inline
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from states import OrderStates

router = Router()

ACTIVE_STATUSES = (
    "pending",
    "waiting_payment",
    "receipt_received",
    "payment_confirmed",
)


def _format_usdt(value) -> str:
    try:
        return f"{Decimal(str(value)):,.3f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.000"


def _format_rate(value) -> str:
    try:
        return f"{Decimal(str(value)):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


async def _get_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, language, terms_accepted, is_blocked, is_verified "
            "FROM users WHERE telegram_id = $1",
            telegram_id,
        )


async def _show_main_menu(callback: CallbackQuery, lang: str):
    await callback.message.answer(
        locale_service.get("main_menu", lang),
        reply_markup=main_menu_inline(lang),
    )
    await callback.message.answer("👇", reply_markup=compact_reply_keyboard(lang))


@router.callback_query(F.data.in_({"menu_rate", "quick_rate"}))
async def show_current_rate(callback: CallbackQuery):
    """Show the canonical USD/NEW.SYP rate without legacy SYP wording."""
    user = await _get_user(callback.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT rate, updated_at FROM exchange_rates ORDER BY id DESC LIMIT 1"
        )

    if not row:
        unavailable = (
            "❌ سعر الصرف غير متوفر حالياً."
            if lang == "ar" else
            "❌ The exchange rate is currently unavailable."
        )
        await callback.answer(unavailable, show_alert=True)
        return

    rate = _format_rate(row["rate"])
    updated_at = row["updated_at"].strftime("%Y-%m-%d %H:%M")
    text = (
        f"💱 <b>سعر الصرف الحالي</b>\n\n"
        f"1 USD = <b>{rate} NEW.SYP</b>\n\n"
        f"📅 آخر تحديث: {updated_at}"
        if lang == "ar" else
        f"💱 <b>Current Exchange Rate</b>\n\n"
        f"1 USD = <b>{rate} NEW.SYP</b>\n\n"
        f"📅 Last updated: {updated_at}"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await _show_main_menu(callback, lang)
    await callback.answer()


@router.callback_query(F.data.in_({"cancel", "cancel_order"}))
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Localize cancellation and return the customer to a clean menu."""
    await state.clear()
    user = await _get_user(callback.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"
    text = "❌ تم إلغاء العملية." if lang == "ar" else "❌ The action was cancelled."
    if callback.data == "cancel_order":
        text = "❌ تم إلغاء الطلب." if lang == "ar" else "❌ The order was cancelled."
    await callback.message.edit_text(text)
    await _show_main_menu(callback, lang)
    await callback.answer()


@router.callback_query(F.data == "quick_reorder")
async def safe_quick_reorder(callback: CallbackQuery, state: FSMContext):
    """Reorder only when the user has no active order and has a verified saved wallet."""
    user = await _get_user(callback.from_user.id)
    if not user:
        await callback.message.edit_text(
            "يرجى بدء البوت أولاً: /start" if user is None else "",
        )
        await callback.answer()
        return

    lang = user["language"] or "ar"
    if not user["terms_accepted"] or user["is_blocked"] or not user["is_verified"]:
        from handlers.order import start_order
        await callback.message.edit_text(
            "↩️ سيتم نقلك إلى مسار إنشاء الطلب." if lang == "ar" else "↩️ Returning you to the order flow."
        )
        await callback.answer()
        await start_order(callback.message, state)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        active = await conn.fetchrow(
            "SELECT order_number, amount_usdt, status FROM orders "
            "WHERE user_id = $1 AND status = ANY($2) "
            "ORDER BY created_at DESC LIMIT 1",
            user["id"], ACTIVE_STATUSES,
        )
        if active:
            status_map = {
                "pending": "بانتظار موافقة الإدارة",
                "waiting_payment": "بانتظار الدفع ورفع الإيصال",
                "receipt_received": "الإيصال قيد المراجعة",
                "payment_confirmed": "بانتظار إرسال USDT من الإدارة",
            }
            status_map_en = {
                "pending": "Awaiting admin approval",
                "waiting_payment": "Awaiting payment and receipt upload",
                "receipt_received": "Receipt under admin review",
                "payment_confirmed": "Awaiting USDT transfer by admin",
            }
            status = (status_map if lang == "ar" else status_map_en).get(active["status"], active["status"])
            amount = _format_usdt(active["amount_usdt"])
        else:
            last_order = await conn.fetchrow(
                """SELECT o.network, o.amount_usdt, o.wallet_address
                   FROM orders o
                   WHERE o.user_id = $1
                   ORDER BY o.created_at DESC LIMIT 1""",
                user["id"],
            )
            last_order = last_order

            if last_order:
                wallet = await conn.fetchrow(
                    """SELECT id, address, network, qr_photo_id
                       FROM saved_addresses
                       WHERE user_id = $1 AND address = $2 AND network = $3
                         AND deleted_at IS NULL
                         AND verification_status = 'verified'
                         AND qr_photo_id IS NOT NULL
                       ORDER BY is_default DESC, created_at DESC LIMIT 1""",
                    user["id"], last_order["wallet_address"], last_order["network"],
                )
            else:
                wallet = None

    if active:
        text = (
            "⚠️ <b>لديك طلب نشط بالفعل</b>\n\n"
            f"📦 الطلب: <b>#{active['order_number']}</b>\n"
            f"💰 المبلغ: <b>{amount} USDT</b>\n"
            f"📊 الحالة: <b>{status}</b>\n\n"
            "📋 افتح <b>طلباتي</b> لمتابعة حالته. لا يمكنك إنشاء طلب جديد قبل اكتماله."
            if lang == "ar" else
            "⚠️ <b>You already have an active order</b>\n\n"
            f"📦 Order: <b>#{active['order_number']}</b>\n"
            f"💰 Amount: <b>{amount} USDT</b>\n"
            f"📊 Status: <b>{status}</b>\n\n"
            "📋 Open <b>Orders</b> to follow it. You cannot create a new order until it is completed."
        )
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.message.answer("👇", reply_markup=compact_reply_keyboard(lang))
        await callback.answer()
        return

    if not last_order or not wallet:
        text = (
            "⚠️ <b>لا يمكن إعادة الطلب تلقائياً</b>\n\n"
            "يجب أن تكون محفظة الطلب السابق محفوظة وموثقة مع QR حتى نستخدمها بأمان.\n\n"
            "افتح <b>👛 محافظي</b> واختر محفظة موثقة، ثم ابدأ طلباً جديداً."
            if lang == "ar" else
            "⚠️ <b>Automatic reorder is unavailable</b>\n\n"
            "The previous wallet must be saved and verified with its QR before it can be reused safely.\n\n"
            "Open <b>My Wallets</b>, choose a verified wallet, then start a new order."
        )
        await callback.message.edit_text(text, parse_mode="HTML")
        await _show_main_menu(callback, lang)
        await callback.answer()
        return

    await state.update_data(
        network=wallet["network"],
        amount_usdt=last_order["amount_usdt"],
        wallet_address=wallet["address"],
        wallet_qr_photo_id=wallet["qr_photo_id"],
        address_from_saved=True,
        wallet_id=wallet["id"],
        saved_address_id=wallet["id"],
    )
    amount = _format_usdt(last_order["amount_usdt"])
    text = (
        "🔄 <b>إعادة طلب آمنة</b>\n\n"
        f"💰 المبلغ: <b>{amount} USDT</b>\n"
        f"🌐 الشبكة: <b>{wallet['network']}</b>\n"
        "✅ تم استخدام المحفظة الموثقة وQR المحفوظ.\n\n"
        "اختر الآن عملة الدفع."
        if lang == "ar" else
        "🔄 <b>Safe Reorder</b>\n\n"
        f"💰 Amount: <b>{amount} USDT</b>\n"
        f"🌐 Network: <b>{wallet['network']}</b>\n"
        "✅ Your verified wallet and stored QR will be reused.\n\n"
        "Now choose the payment currency."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.message.answer(
        locale_service.get("select_currency", lang),
        reply_markup=currency_selection_keyboard(lang),
    )
    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()
