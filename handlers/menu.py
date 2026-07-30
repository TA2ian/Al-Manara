"""User menu, navigation, and quick actions."""
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from keyboards.inline import main_menu_inline, settings_keyboard, cancel_keyboard, saved_addresses_keyboard
from states import OrderStates
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from database import get_pool
from config import Config

logger = logging.getLogger(__name__)
router = Router()


def get_user_lang(data: dict) -> str:
    """Get user language from event data."""
    user = data.get('event_from_user', None)
    # Attempt to get language from DB via middleware-injected user
    user_data = data.get('user', {})
    if isinstance(user_data, dict) and 'language' in user_data:
        return user_data['language']
    return 'ar'


# ───── General Cancel/Back ─────

@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Cancel current action and clear state."""
    await state.clear()
    await callback.message.edit_text("❌ تم الإلغاء.")
    lang = 'ar'
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", callback.from_user.id)
            if user:
                lang = user['language']
    except Exception:
        pass
    await callback.message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "back")
async def back_action(callback: CallbackQuery, state: FSMContext):
    """Go back to main menu."""
    await state.clear()
    lang = 'ar'
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", callback.from_user.id)
            if user:
                lang = user['language']
    except Exception:
        pass
    await callback.message.edit_text(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_order")
async def cancel_order_action(callback: CallbackQuery, state: FSMContext):
    """Cancel order creation."""
    await state.clear()
    lang = 'ar'
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", callback.from_user.id)
            if user:
                lang = user['language']
    except Exception:
        pass
    await callback.message.edit_text("❌ تم إلغاء الطلب.")
    await callback.message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_wallet")
async def back_to_wallet(callback: CallbackQuery, state: FSMContext):
    """Go back to wallet input step."""
    data = await state.get_data()
    lang = 'ar'
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", callback.from_user.id)
            if user:
                lang = user['language']
    except Exception:
        pass

    network = data.get('network', 'BEP20')
    example = locale_service.get('bep20_example' if network == 'BEP20' else 'trc20_example', lang)
    await callback.message.edit_text(
        locale_service.get('enter_wallet', lang, network=network, example=example),
        reply_markup=cancel_keyboard(lang),
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.waiting_wallet)
    await callback.answer()


# ───── Main Menu Handlers ─────

@router.callback_query(F.data == "menu_rate")
@router.callback_query(F.data == "quick_rate")
async def show_rate(callback: CallbackQuery):
    """Show current exchange rate."""
    pool = await get_pool()
    lang = 'ar'

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1", callback.from_user.id
        )
        if user:
            lang = user['language']

        rate_row = await conn.fetchrow(
            "SELECT rate, updated_at FROM exchange_rates ORDER BY id DESC LIMIT 1"
        )

    if not rate_row:
        await callback.answer("❌ سعر الصرف غير متوفر حالياً.", show_alert=True)
        return

    updated_at = rate_row['updated_at'].strftime('%Y-%m-%d %H:%M')
    rate_text = (
        f"💱 <b>سعر الصرف الحالي</b>\n\n"
        f"1 USDT = {rate_row['rate']:,.0f} SYP\n\n"
        f"📅 آخر تحديث: {updated_at}"
    )

    await callback.message.edit_text(rate_text, parse_mode='HTML')
    await callback.message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "menu_support")
@router.callback_query(F.data == "quick_contact")
async def show_support(callback: CallbackQuery):
    """Show support contact info with pre-filled template."""
    lang = 'ar'
    extra_data = ""
    full_name = "N/A"
    username = "N/A"
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT language, full_name, username FROM users WHERE telegram_id = $1",
                callback.from_user.id
            )
            if user:
                lang = user['language']
                full_name = user['full_name'] or 'N/A'
                username = user['username'] or 'N/A'

                # Fetch last active order if any
                order = await conn.fetchrow(
                    "SELECT order_number, amount_usdt, status, created_at "
                    "FROM orders WHERE user_id = (SELECT id FROM users WHERE telegram_id = $1) "
                    "AND status != 'completed' AND status != 'rejected' "
                    "ORDER BY created_at DESC LIMIT 1",
                    callback.from_user.id
                )
                if order:
                    status_names_ar = {
                        'pending': 'قيد الانتظار',
                        'waiting_payment': 'في انتظار الدفع',
                        'receipt_received': 'الإيصال قيد المراجعة',
                        'payment_confirmed': 'تم تأكيد الدفع',
                    }
                    status_names_en = {
                        'pending': 'Pending',
                        'waiting_payment': 'Awaiting Payment',
                        'receipt_received': 'Receipt Under Review',
                        'payment_confirmed': 'Payment Confirmed',
                    }
                    status_map = status_names_ar if lang == 'ar' else status_names_en
                    extra_data = (
                        f"آخر طلب: #{order['order_number']} — {order['amount_usdt']} USDT"
                        if lang == 'ar' else
                        f"Last Order: #{order['order_number']} — {order['amount_usdt']} USDT"
                    )
                    extra_data += f"\nالحالة: {status_map.get(order['status'], order['status'])}" if lang == 'ar' \
                        else f"\nStatus: {status_map.get(order['status'], order['status'])}"
                    extra_data += f"\nالتاريخ: {order['created_at'].strftime('%Y-%m-%d %H:%M')}" if lang == 'ar' \
                        else f"\nDate: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
    except Exception:
        pass

    support_text = locale_service.get('support_contact', lang)
    await callback.message.edit_text(support_text, parse_mode='HTML')

    # Show pre-filled support template
    template = locale_service.get(
        'support_template', lang,
        full_name=full_name,
        telegram_id=callback.from_user.id,
        username=username,
        extra_data=extra_data or ("لا يوجد طلبات نشطة" if lang == 'ar' else "No active orders")
    )
    await callback.message.answer(template, parse_mode='HTML')

    # Re-send reply keyboard so it stays visible at the bottom
    await callback.message.answer(
        "👇",
        reply_markup=compact_reply_keyboard(lang)
    )
    await callback.message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "menu_disclaimer")
async def show_disclaimer(callback: CallbackQuery):
    """Show disclaimer / terms of service."""
    lang = 'ar'
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT language FROM users WHERE telegram_id = $1", callback.from_user.id
            )
            if user:
                lang = user['language']
    except Exception:
        pass

    text = locale_service.get('terms_text', lang,
                              min_order=Config.MIN_ORDER,
                              max_order=Config.MAX_ORDER,
                              timeout=Config.PAYMENT_TIMEOUT)
    await callback.message.edit_text(text, parse_mode='HTML')
    await callback.message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "menu_help")
async def show_help(callback: CallbackQuery):
    """Show help text."""
    lang = 'ar'
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT language FROM users WHERE telegram_id = $1", callback.from_user.id
            )
            if user:
                lang = user['language']
    except Exception:
        pass

    help_text = locale_service.get('help_text', lang)
    await callback.message.edit_text(help_text, parse_mode='HTML')
    await callback.message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "quick_reorder")
async def quick_reorder(callback: CallbackQuery, state: FSMContext):
    """Quick reorder from last order."""
    pool = await get_pool()
    lang = 'ar'

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1", callback.from_user.id
        )
        if user:
            lang = user['language']

        last_order = await conn.fetchrow(
            "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
            user['id']
        )

    if not last_order:
        await callback.answer("❌ لا يوجد طلب سابق لإعادة الطلب.", show_alert=True)
        return

    # Pre-fill state with last order data and start new order
    await state.update_data(
        network=last_order['network'],
        amount_usdt=last_order['amount_usdt'],
        wallet_address=last_order['wallet_address'],
    )

    await callback.message.edit_text(
        f"🔄 تم تعبئة بيانات آخر طلب:\n"
        f"🌐 {last_order['network']}\n"
        f"💰 {last_order['amount_usdt']} USDT\n"
        f"📍 <code>{last_order['wallet_address'][:12]}...</code>\n\n"
        f"اختر عملة الدفع:",
        parse_mode='HTML'
    )

    from keyboards.inline import currency_selection_keyboard
    await callback.message.answer(
        locale_service.get('select_currency', lang),
        reply_markup=currency_selection_keyboard(lang)
    )
    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()


@router.callback_query(F.data == "quick_wallet")
async def quick_wallet(callback: CallbackQuery):
    """Show user's last used wallet."""
    pool = await get_pool()
    lang = 'ar'

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1", callback.from_user.id
        )
        if user:
            lang = user['language']

        last_order = await conn.fetchrow(
            "SELECT wallet_address, network FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
            user['id']
        )

    if not last_order:
        await callback.answer("❌ لا يوجد عنوان محفظة مسجل.", show_alert=True)
        return

    await callback.message.edit_text(
        f"📍 <b>آخر عنوان مستخدم</b>\n\n"
        f"🌐 الشبكة: {last_order['network']}\n"
        f"📬 العنوان:\n<code>{last_order['wallet_address']}</code>",
        parse_mode='HTML'
    )
    await callback.answer()


# ───── ⚙️ Settings Button (Reply Keyboard) ─────

@router.message(F.text.func(lambda t: '⚙' in t))
async def settings_button(message: Message):
    """Handle the ⚙️ settings button from reply keyboard."""
    pool = await get_pool()
    lang = 'ar'

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1", message.from_user.id
        )
        if user:
            lang = user['language']

    # Check if admin
    if message.from_user.id in Config.ADMIN_IDS:
        from keyboards.inline import admin_menu_keyboard
        await message.answer(
            "⚙️ <b>القائمة</b>",
            reply_markup=main_menu_inline(lang),
            parse_mode='HTML'
        )
        await message.answer(
            "👤 <b>لوحة المسؤول</b>\n"
            "استخدم /admin للوحة التحكم.",
            parse_mode='HTML'
        )
        return

    # Regular user - show quick actions
    from keyboards.inline import quick_actions_keyboard
    await message.answer(
        "⚙️ <b>" + ("إجراءات سريعة" if lang == 'ar' else "Quick Actions") + "</b>",
        reply_markup=quick_actions_keyboard(lang),
        parse_mode='HTML'
    )


# ───── Language Change ─────

@router.callback_query(F.data == "quick_change_lang")
async def change_language_prompt(callback: CallbackQuery):
    """Show language selection for changing language."""
    await callback.message.edit_text(
        locale_service.get('change_language', 'ar'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")
            ]
        ]),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_lang_"))
async def set_language(callback: CallbackQuery):
    """Update user language preference and refresh UI."""
    new_lang = callback.data.replace("set_lang_", "")
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET language = $1 WHERE telegram_id = $2",
            new_lang, callback.from_user.id
        )

    await callback.message.edit_text(
        locale_service.get('language_changed', new_lang),
        parse_mode='HTML'
    )
    await callback.message.answer(
        locale_service.get('main_menu', new_lang),
        reply_markup=main_menu_inline(new_lang)
    )
    await callback.answer()


# ───── Saved Addresses ─────

@router.callback_query(F.data == "quick_saved_addresses")
async def show_saved_addresses(callback: CallbackQuery):
    """Show user's saved addresses."""
    pool = await get_pool()
    lang = 'ar'

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1", callback.from_user.id
        )
        if user:
            lang = user['language']
            addresses = await conn.fetch(
                "SELECT id, address, network, label, created_at FROM saved_addresses "
                "WHERE user_id = $1 ORDER BY created_at DESC",
                user['id']
            )

    if not addresses:
        await callback.message.edit_text(
            locale_service.get('no_saved_addresses', lang),
            parse_mode='HTML'
        )
        await callback.message.answer(
            locale_service.get('main_menu', lang),
            reply_markup=main_menu_inline(lang)
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        locale_service.get('saved_addresses_title', lang),
        parse_mode='HTML'
    )
    await callback.message.answer(
        "📍 " + ("اختر عنواناً:" if lang == 'ar' else "Select an address:"),
        reply_markup=saved_addresses_keyboard(addresses, lang),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_addr_"))
async def view_saved_address(callback: CallbackQuery):
    """Show details of a saved address."""
    addr_id = int(callback.data.replace("view_addr_", ""))
    pool = await get_pool()
    lang = 'ar'

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1", callback.from_user.id
        )
        if user:
            lang = user['language']
            addr = await conn.fetchrow(
                "SELECT address, network, label, created_at FROM saved_addresses "
                "WHERE id = $1 AND user_id = $2",
                addr_id, user['id']
            )

    if not addr:
        await callback.answer("❌ " + ("العنوان غير موجود" if lang == 'ar' else "Address not found"), show_alert=True)
        return

    label = addr['label'] or ('بدون تصنيف' if lang == 'ar' else 'No label')
    date = addr['created_at'].strftime('%Y-%m-%d %H:%M')
    full = addr['address']
    address_display = f"<b>{full[:6]}</b>{full[6:-4]}<b>{full[-4:]}</b>"

    from keyboards.inline import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=locale_service.get('delete_address', lang), callback_data=f"del_addr_{addr_id}"),
            InlineKeyboardButton(text=locale_service.get('back', lang), callback_data="quick_saved_addresses")
        ]
    ])

    await callback.message.edit_text(
        locale_service.get('address_details', lang, network=addr['network'], address=address_display, date=date, label=label),
        parse_mode='HTML',
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_addr_conf_"))
async def delete_saved_address_execute(callback: CallbackQuery):
    """Actually delete the saved address."""
    addr_id = int(callback.data.replace("del_addr_conf_", ""))
    pool = await get_pool()
    lang = 'ar'

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1", callback.from_user.id
        )
        if user:
            lang = user['language']
            await conn.execute(
                "DELETE FROM saved_addresses WHERE id = $1 AND user_id = $2",
                addr_id, user['id']
            )

    await callback.message.edit_text(
        locale_service.get('delete_address_done', lang),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_addr_"))
async def delete_saved_address_confirm(callback: CallbackQuery):
    """Ask for delete confirmation."""
    addr_id = int(callback.data.replace("del_addr_", ""))
    # Skip if this is actually a del_addr_conf_ callback that was caught
    if callback.data.startswith("del_addr_conf_"):
        return
    lang = 'ar'
    await callback.message.edit_text(
        locale_service.get('delete_address_confirm', lang),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=locale_service.get('delete_address_confirm_btn', lang), callback_data=f"del_addr_conf_{addr_id}"),
                InlineKeyboardButton(text=locale_service.get('cancel', lang), callback_data="quick_saved_addresses")
            ]
        ])
    )
    await callback.answer()
