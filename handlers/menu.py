"""User menu, navigation, and quick actions."""
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from keyboards.inline import main_menu_inline, settings_keyboard, cancel_keyboard, back_keyboard
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
        reply_markup=cancel_keyboard(lang)
    )
    await state.set_state('OrderStates:waiting_wallet')
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
    """Show support contact info."""
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

    support_text = locale_service.get('support_contact', lang)
    await callback.message.edit_text(support_text, parse_mode='HTML')
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
    await state.set_state('OrderStates:waiting_currency')
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

@router.message(F.text == "⚙️")
async def settings_button(message: Message):
    """Handle the ⚙️ settings button from reply keyboard."""
    pool = await get_pool()
    lang = 'ar'

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT language, is_admin FROM users WHERE telegram_id = $1", message.from_user.id
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
        "⚙️ <b>إجراءات سريعة</b>",
        reply_markup=quick_actions_keyboard(lang),
        parse_mode='HTML'
    )
