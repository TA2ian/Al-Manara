"""Legacy customer menu compatibility router.

Authoritative customer navigation, language, and wallet-order flows live in
policy routers registered before this compatibility router. This module keeps
only legacy UI callbacks that still have no dedicated authoritative owner.
"""
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards.inline import main_menu_inline, saved_addresses_keyboard
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from database import get_pool
from config import Config

logger = logging.getLogger(__name__)
router = Router()


async def _get_lang(user_id: int) -> str:
    pool = await get_pool()
    if not pool:
        return "ar"
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", user_id)
    return (row["language"] if row and row["language"] else "ar")


@router.callback_query(F.data == "menu_support")
@router.callback_query(F.data == "quick_contact")
async def show_support(callback: CallbackQuery):
    """Show support contact info with pre-filled template."""
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
                    "SELECT order_number, amount_usdt, status, created_at "
                    "FROM orders WHERE user_id = (SELECT id FROM users WHERE telegram_id = $1) "
                    "AND status != 'completed' AND status != 'rejected' "
                    "ORDER BY created_at DESC LIMIT 1",
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
                        if lang == "ar"
                        else {
                            "pending": "Pending",
                            "waiting_payment": "Awaiting Payment",
                            "receipt_received": "Receipt Under Review",
                            "payment_confirmed": "Payment Confirmed",
                        }
                    )
                    if lang == "ar":
                        extra_data = (
                            f"آخر طلب: #{order['order_number']} — {order['amount_usdt']} USDT\n"
                            f"الحالة: {status_names.get(order['status'], order['status'])}\n"
                            f"التاريخ: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
                        )
                    else:
                        extra_data = (
                            f"Last Order: #{order['order_number']} — {order['amount_usdt']} USDT\n"
                            f"Status: {status_names.get(order['status'], order['status'])}\n"
                            f"Date: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
                        )
    except Exception:
        logger.exception("Failed to build support context")

    await callback.message.edit_text(
        locale_service.get("support_contact", lang),
        parse_mode="HTML",
    )
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
    await callback.message.answer(
        locale_service.get("main_menu", lang),
        reply_markup=main_menu_inline(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "menu_disclaimer")
async def show_disclaimer(callback: CallbackQuery):
    """Show disclaimer / terms of service."""
    lang = await _get_lang(callback.from_user.id)
    text = locale_service.get(
        "terms_text",
        lang,
        min_order=Config.MIN_ORDER,
        max_order=Config.MAX_ORDER,
        timeout=Config.PAYMENT_TIMEOUT,
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.message.answer(
        locale_service.get("main_menu", lang),
        reply_markup=main_menu_inline(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "menu_help")
async def show_help(callback: CallbackQuery):
    """Show help text."""
    lang = await _get_lang(callback.from_user.id)
    await callback.message.edit_text(locale_service.get("help_text", lang), parse_mode="HTML")
    await callback.message.answer(
        locale_service.get("main_menu", lang),
        reply_markup=main_menu_inline(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "quick_saved_addresses")
async def show_saved_addresses(callback: CallbackQuery):
    """Legacy entry point for the saved-address list."""
    pool = await get_pool()
    lang = await _get_lang(callback.from_user.id)
    addresses = []
    if pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1",
                callback.from_user.id,
            )
            if user:
                addresses = await conn.fetch(
                    "SELECT id, address, network, label, created_at FROM saved_addresses "
                    "WHERE user_id = $1 AND deleted_at IS NULL "
                    "ORDER BY created_at DESC",
                    user["id"],
                )

    if not addresses:
        await callback.message.edit_text(
            locale_service.get("no_saved_addresses", lang),
            parse_mode="HTML",
        )
        await callback.message.answer(
            locale_service.get("main_menu", lang),
            reply_markup=main_menu_inline(lang),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        locale_service.get("saved_addresses_title", lang),
        parse_mode="HTML",
    )
    await callback.message.answer(
        "📍 " + ("اختر عنواناً:" if lang == "ar" else "Select an address:"),
        reply_markup=saved_addresses_keyboard(addresses, lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_addr_"))
async def view_saved_address(callback: CallbackQuery):
    """Show details for a saved address from the legacy UI."""
    try:
        addr_id = int(callback.data.removeprefix("view_addr_"))
    except ValueError:
        await callback.answer("Invalid address", show_alert=True)
        return

    pool = await get_pool()
    lang = await _get_lang(callback.from_user.id)
    addr = None
    if pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1",
                callback.from_user.id,
            )
            if user:
                addr = await conn.fetchrow(
                    "SELECT address, network, label, created_at FROM saved_addresses "
                    "WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL",
                    addr_id,
                    user["id"],
                )

    if not addr:
        await callback.answer(
            "❌ " + ("العنوان غير موجود" if lang == "ar" else "Address not found"),
            show_alert=True,
        )
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    label = addr["label"] or ("بدون تصنيف" if lang == "ar" else "No label")
    date = addr["created_at"].strftime("%Y-%m-%d %H:%M")
    full = addr["address"]
    address_display = f"<b>{full[:6]}</b>{full[6:-4]}<b>{full[-4:]}</b>"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=locale_service.get("delete_address", lang),
                    callback_data=f"del_addr_{addr_id}",
                ),
                InlineKeyboardButton(
                    text=locale_service.get("back", lang),
                    callback_data="quick_saved_addresses",
                ),
            ]
        ]
    )
    await callback.message.edit_text(
        locale_service.get(
            "address_details",
            lang,
            network=addr["network"],
            address=address_display,
            date=date,
            label=label,
        ),
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_addr_conf_"))
async def delete_saved_address_execute(callback: CallbackQuery):
    """Delete a saved address after explicit confirmation."""
    try:
        addr_id = int(callback.data.removeprefix("del_addr_conf_"))
    except ValueError:
        await callback.answer("Invalid address", show_alert=True)
        return

    pool = await get_pool()
    lang = await _get_lang(callback.from_user.id)
    if pool:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1",
                callback.from_user.id,
            )
            if user:
                await conn.execute(
                    "UPDATE saved_addresses SET deleted_at = NOW(), updated_at = NOW() "
                    "WHERE id = $1 AND user_id = $2",
                    addr_id,
                    user["id"],
                )

    await callback.message.edit_text(
        locale_service.get("delete_address_done", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_addr_"))
async def delete_saved_address_confirm(callback: CallbackQuery):
    """Ask for address deletion confirmation."""
    try:
        addr_id = int(callback.data.removeprefix("del_addr_"))
    except ValueError:
        await callback.answer("Invalid address", show_alert=True)
        return
    lang = await _get_lang(callback.from_user.id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    await callback.message.edit_text(
        locale_service.get("delete_address_confirm", lang),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=locale_service.get("delete_address_confirm_btn", lang),
                        callback_data=f"del_addr_conf_{addr_id}",
                    ),
                    InlineKeyboardButton(
                        text=locale_service.get("cancel", lang),
                        callback_data="quick_saved_addresses",
                    ),
                ]
            ]
        ),
    )
    await callback.answer()
