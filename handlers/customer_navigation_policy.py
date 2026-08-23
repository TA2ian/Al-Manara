"""Authoritative customer navigation policy."""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from database import get_pool
from keyboards.inline import currency_selection_keyboard, main_menu_inline, saved_addresses_keyboard
from keyboards.reply import compact_reply_keyboard
from services.formatters import rate as format_rate, usdt
from services.locale_service import locale_service
from states import OrderStates

router = Router()
logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (
    "pending",
    "waiting_payment",
    "receipt_received",
    "payment_confirmed",
)


async def _get_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, language, terms_accepted, is_blocked, is_verified FROM users WHERE telegram_id = $1",
            telegram_id,
        )


async def _get_lang(user_id: int) -> str:
    user = await _get_user(user_id)
    return (user["language"] if user and user["language"] else "ar")


async def _show_main_menu(callback: CallbackQuery, lang: str):
    await callback.message.answer(locale_service.get("main_menu", lang), reply_markup=main_menu_inline(lang))
    await callback.message.answer("👇", reply_markup=compact_reply_keyboard(lang))


@router.callback_query(F.data.in_({"menu_rate", "quick_rate"}))
async def show_current_rate(callback: CallbackQuery):
    user = await _get_user(callback.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT rate, updated_at, rate_currency FROM exchange_rates ORDER BY id DESC LIMIT 1")

    if not row or (row["rate_currency"] or "NEW.SYP") not in ("NEW.SYP", "SYP"):
        await callback.answer("❌ سعر الصرف غير متوفر حالياً." if lang == "ar" else "❌ The exchange rate is currently unavailable.", show_alert=True)
        return

    current_rate = row["rate"]
    if (row["rate_currency"] or "NEW.SYP") == "SYP":
        from decimal import Decimal
        current_rate = Decimal(str(current_rate)) / Decimal("100")
    text = (
        f"💱 <b>سعر الصرف الحالي</b>\n\n1 USD = <b>{format_rate(current_rate)} NEW.SYP</b>\n\n"
        f"📅 آخر تحديث: {row['updated_at'].strftime('%Y-%m-%d %H:%M')}"
        if lang == "ar" else
        f"💱 <b>Current Exchange Rate</b>\n\n1 USD = <b>{format_rate(current_rate)} NEW.SYP</b>\n\n"
        f"📅 Last updated: {row['updated_at'].strftime('%Y-%m-%d %H:%M')}"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await _show_main_menu(callback, lang)
    await callback.answer()


@router.callback_query(F.data.in_({"cancel", "cancel_order"}))
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await _get_user(callback.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"
    text = "❌ تم إلغاء الطلب." if callback.data == "cancel_order" and lang == "ar" else (
        "❌ The order was cancelled." if callback.data == "cancel_order" else (
            "❌ تم إلغاء العملية." if lang == "ar" else "❌ The action was cancelled."
        )
    )
    await callback.message.edit_text(text)
    await _show_main_menu(callback, lang)
    await callback.answer()


@router.callback_query(F.data == "quick_reorder")
async def safe_quick_reorder(callback: CallbackQuery, state: FSMContext):
    """Reuse only a verified saved wallet and always enter the authoritative order flow."""
    user = await _get_user(callback.from_user.id)
    if not user:
        await callback.message.edit_text("يرجى بدء البوت أولاً: /start")
        await callback.answer()
        return

    lang = user["language"] or "ar"
    if not user["terms_accepted"] or user["is_blocked"] or not user["is_verified"]:
        from handlers.order_amount_policy import start_order_authoritative
        await callback.message.edit_text("↩️ سيتم نقلك إلى مسار إنشاء الطلب." if lang == "ar" else "↩️ Returning you to the order flow.")
        await callback.answer()
        await start_order_authoritative(callback.message, state)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        active = await conn.fetchrow(
            "SELECT order_number, amount_usdt, status FROM orders WHERE user_id = $1 AND status = ANY($2) ORDER BY created_at DESC LIMIT 1",
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
        else:
            last_order = await conn.fetchrow(
                "SELECT o.network, o.amount_usdt, o.wallet_address FROM orders o WHERE o.user_id = $1 ORDER BY o.created_at DESC LIMIT 1",
                user["id"],
            )
            wallet = None
            if last_order:
                wallet = await conn.fetchrow(
                    """SELECT id, address, network, qr_photo_id FROM saved_addresses
                       WHERE user_id = $1 AND address = $2 AND network = $3
                         AND deleted_at IS NULL AND verification_status = 'verified' AND qr_photo_id IS NOT NULL
                       ORDER BY is_default DESC, created_at DESC LIMIT 1""",
                    user["id"], last_order["wallet_address"], last_order["network"],
                )

    if active:
        text = (
            "⚠️ <b>لديك طلب نشط بالفعل</b>\n\n"
            f"📦 الطلب: <b>#{active['order_number']}</b>\n💰 المبلغ: <b>{usdt(active['amount_usdt'])} USDT</b>\n"
            f"📊 الحالة: <b>{status}</b>\n\n📋 افتح <b>طلباتي</b> لمتابعة حالته."
            if lang == "ar" else
            "⚠️ <b>You already have an active order</b>\n\n"
            f"📦 Order: <b>#{active['order_number']}</b>\n💰 Amount: <b>{usdt(active['amount_usdt'])} USDT</b>\n"
            f"📊 Status: <b>{status}</b>\n\n📋 Open <b>Orders</b> to follow it."
        )
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.message.answer("👇", reply_markup=compact_reply_keyboard(lang))
        await callback.answer()
        return

    if not last_order or not wallet:
        text = (
            "⚠️ <b>لا يمكن إعادة الطلب تلقائياً</b>\n\n"
            "يجب أن تكون محفظة الطلب السابق محفوظة وموثقة مع QR. افتح <b>👛 محافظي</b> ثم ابدأ طلباً جديداً."
            if lang == "ar" else
            "⚠️ <b>Automatic reorder is unavailable</b>\n\n"
            "The previous wallet must be saved and verified with its QR. Open <b>My Wallets</b>, then start a new order."
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
    text = (
        "🔄 <b>إعادة طلب آمنة</b>\n\n"
        f"💰 المبلغ: <b>{usdt(last_order['amount_usdt'])} USDT</b>\n🌐 الشبكة: <b>{wallet['network']}</b>\n"
        "✅ تم استخدام المحفظة الموثقة وQR المحفوظ.\n\nاختر الآن عملة الدفع."
        if lang == "ar" else
        "🔄 <b>Safe Reorder</b>\n\n"
        f"💰 Amount: <b>{usdt(last_order['amount_usdt'])} USDT</b>\n🌐 Network: <b>{wallet['network']}</b>\n"
        "✅ Your verified wallet and stored QR will be reused.\n\nNow choose the payment currency."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.message.answer(locale_service.get("select_currency", lang), reply_markup=currency_selection_keyboard(lang))
    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()


@router.callback_query(F.data.in_({"menu_support", "quick_contact"}))
async def show_support(callback: CallbackQuery):
    """Show support contact information with useful current-order context."""
    lang = await _get_lang(callback.from_user.id)
    extra_data = ""
    full_name = "N/A"
    username = "N/A"
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT language, full_name, username FROM users WHERE telegram_id = $1",
                callback.from_user.id,
            )
            if user:
                lang = user["language"] or lang
                full_name = user["full_name"] or "N/A"
                username = user["username"] or "N/A"
                order = await conn.fetchrow(
                    "SELECT order_number, amount_usdt, status, created_at FROM orders "
                    "WHERE user_id = (SELECT id FROM users WHERE telegram_id = $1) "
                    "AND status NOT IN ('completed', 'rejected') ORDER BY created_at DESC LIMIT 1",
                    callback.from_user.id,
                )
                if order:
                    status_names = (
                        {
                            "pending": "قيد الانتظار",
                            "waiting_payment": "في انتظار الدفع",
                            "receipt_received": "الإيصال قيد المراجعة",
                            "payment_confirmed": "تم تأكيد الدفع",
                        }
                        if lang == "ar" else {
                            "pending": "Pending",
                            "waiting_payment": "Awaiting Payment",
                            "receipt_received": "Receipt Under Review",
                            "payment_confirmed": "Payment Confirmed",
                        }
                    )
                    extra_data = (
                        f"آخر طلب: #{order['order_number']} — {order['amount_usdt']} USDT\n"
                        f"الحالة: {status_names.get(order['status'], order['status'])}\n"
                        f"التاريخ: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
                        if lang == "ar" else
                        f"Last Order: #{order['order_number']} — {order['amount_usdt']} USDT\n"
                        f"Status: {status_names.get(order['status'], order['status'])}\n"
                        f"Date: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
                    )
    except Exception:
        logger.exception("Failed to build support context")

    await callback.message.edit_text(locale_service.get("support_contact", lang), parse_mode="HTML")
    template = locale_service.get(
        "support_template",
        lang,
        full_name=full_name,
        telegram_id=callback.from_user.id,
        username=username,
        extra_data=extra_data or ("لا يوجد طلبات نشطة" if lang == "ar" else "No active orders"),
    )
    await callback.message.answer(template, parse_mode="HTML")
    await callback.message.answer("👇", reply_markup=compact_reply_keyboard(lang))
    await callback.message.answer(locale_service.get("main_menu", lang), reply_markup=main_menu_inline(lang))
    await callback.answer()


@router.callback_query(F.data == "menu_disclaimer")
async def show_disclaimer(callback: CallbackQuery):
    """Show the current disclaimer from the canonical customer navigation router."""
    lang = await _get_lang(callback.from_user.id)
    text = locale_service.get(
        "terms_text",
        lang,
        min_order=Config.MIN_ORDER,
        max_order=Config.MAX_ORDER,
        timeout=Config.PAYMENT_TIMEOUT,
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.message.answer(locale_service.get("main_menu", lang), reply_markup=main_menu_inline(lang))
    await callback.answer()


@router.callback_query(F.data == "menu_help")
async def show_help(callback: CallbackQuery):
    """Show help from the canonical customer navigation router."""
    lang = await _get_lang(callback.from_user.id)
    await callback.message.edit_text(locale_service.get("help_text", lang), parse_mode="HTML")
    await callback.message.answer(locale_service.get("main_menu", lang), reply_markup=main_menu_inline(lang))
    await callback.answer()


@router.callback_query(F.data == "quick_saved_addresses")
async def show_saved_addresses(callback: CallbackQuery):
    """Open the verified saved-wallet list from the customer navigation menu."""
    pool = await get_pool()
    lang = await _get_lang(callback.from_user.id)
    addresses = []
    if pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id)
            if user:
                addresses = await conn.fetch(
                    """SELECT id, address, network, label, created_at
                       FROM saved_addresses
                       WHERE user_id = $1 AND deleted_at IS NULL AND verification_status = 'verified'
                       ORDER BY is_default DESC, created_at DESC""",
                    user["id"],
                )

    if not addresses:
        await callback.message.edit_text(locale_service.get("no_saved_addresses", lang), parse_mode="HTML")
        await callback.message.answer(locale_service.get("main_menu", lang), reply_markup=main_menu_inline(lang))
        await callback.answer()
        return

    await callback.message.edit_text(locale_service.get("saved_addresses_title", lang), parse_mode="HTML")
    await callback.message.answer(
        "📍 " + ("اختر عنواناً:" if lang == "ar" else "Select an address:"),
        reply_markup=saved_addresses_keyboard(addresses, lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_addr_"))
async def view_saved_address(callback: CallbackQuery):
    """Show details for a saved wallet."""
    try:
        address_id = int(callback.data.removeprefix("view_addr_"))
    except ValueError:
        await callback.answer("Invalid address", show_alert=True)
        return

    pool = await get_pool()
    lang = await _get_lang(callback.from_user.id)
    address = None
    if pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id)
            if user:
                address = await conn.fetchrow(
                    """SELECT address, network, label, created_at
                       FROM saved_addresses
                       WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL AND verification_status = 'verified'""",
                    address_id,
                    user["id"],
                )

    if not address:
        await callback.answer("❌ " + ("العنوان غير موجود" if lang == "ar" else "Address not found"), show_alert=True)
        return

    label = address["label"] or ("بدون تصنيف" if lang == "ar" else "No label")
    created_at = address["created_at"].strftime("%Y-%m-%d %H:%M")
    full = address["address"]
    address_display = f"<b>{full[:6]}</b>{full[6:-4]}<b>{full[-4:]}</b>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=locale_service.get("delete_address", lang), callback_data=f"del_addr_{address_id}"),
        InlineKeyboardButton(text=locale_service.get("back", lang), callback_data="quick_saved_addresses"),
    ]])
    await callback.message.edit_text(
        locale_service.get(
            "address_details",
            lang,
            network=address["network"],
            address=address_display,
            date=created_at,
            label=label,
        ),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_addr_conf_"))
async def delete_saved_address_execute(callback: CallbackQuery):
    """Delete a saved wallet after explicit confirmation."""
    try:
        address_id = int(callback.data.removeprefix("del_addr_conf_"))
    except ValueError:
        await callback.answer("Invalid address", show_alert=True)
        return

    pool = await get_pool()
    lang = await _get_lang(callback.from_user.id)
    if pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id)
            if user:
                await conn.execute(
                    "UPDATE saved_addresses SET deleted_at = NOW(), updated_at = NOW() WHERE id = $1 AND user_id = $2",
                    address_id,
                    user["id"],
                )

    await callback.message.edit_text(locale_service.get("delete_address_done", lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("del_addr_"))
async def delete_saved_address_confirm(callback: CallbackQuery):
    """Ask for saved-wallet deletion confirmation."""
    try:
        address_id = int(callback.data.removeprefix("del_addr_"))
    except ValueError:
        await callback.answer("Invalid address", show_alert=True)
        return
    lang = await _get_lang(callback.from_user.id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=locale_service.get("delete_address_confirm_btn", lang), callback_data=f"del_addr_conf_{address_id}"),
        InlineKeyboardButton(text=locale_service.get("cancel", lang), callback_data="quick_saved_addresses"),
    ]])
    await callback.message.edit_text(
        locale_service.get("delete_address_confirm", lang),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer()
