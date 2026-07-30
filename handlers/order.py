"""Order creation handlers."""
import uuid
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import OrderStates
from keyboards.inline import (
    network_selection_keyboard,
    currency_selection_keyboard,
    order_confirmation_keyboard,
    cancel_keyboard,
    main_menu_inline,
    order_admin_keyboard,
    saved_addresses_keyboard,
    preset_amounts_keyboard,
)
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from services.wallet_validator import WalletValidator
from services.exchange_service import ExchangeService
from services.notification_service import NotificationService
from config import Config
from database import get_pool
from keyboards.inline import start_verification_keyboard
from middleware.rate_limit import rate_limiter as global_rate_limiter

router = Router()


def generate_order_number() -> str:
    """Generate unique order number with underscores for hashtag compatibility."""
    return f"ORD_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6].upper()}"


@router.message(F.text.in_(["💰 جديد", "💰 New", "💰 إنشاء طلب شراء", "💰 Buy Order"]))
async def start_order(message: Message, state: FSMContext):
    """Start new order."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

    if not user or not user['terms_accepted']:
        await message.answer("يرجى قبول الشروط أولاً: /start")
        return

    if user.get('is_blocked', False):
        lang = user.get('language', 'ar')
        support = locale_service.get('support_contact', lang)
        await message.answer(
            locale_service.get('user_blocked', lang) + "\n\n" + support,
            parse_mode='HTML'
        )
        return

    if not user['is_verified']:
        await message.answer(
            "🔒 <b>يرجى إكمال التوثيق أولاً</b>\n\nلإنشاء طلب، يجب توثيق حسابك أولاً عبر إرسال اسمك ورقم شام كاش.",
            parse_mode='HTML',
            reply_markup=start_verification_keyboard(user['language'])
        )
        return

    lang = user['language']

    await message.answer(
        locale_service.get('select_network', lang),
        reply_markup=network_selection_keyboard(lang),
        parse_mode='HTML'
    )

    await state.set_state(OrderStates.waiting_network)


async def _get_user_lang(telegram_id: int) -> str:
    """Fetch user language from DB."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT language FROM users WHERE telegram_id = $1", telegram_id)
            if user:
                return user['language']
    except Exception:
        pass
    return 'ar'


@router.callback_query(OrderStates.waiting_network, F.data.startswith("network_"))
async def select_network(callback: CallbackQuery, state: FSMContext):
    """Handle network selection."""
    allowed, _ = global_rate_limiter.check(callback.from_user.id, 'order_network')
    if not allowed:
        await callback.answer()
        return

    network = callback.data.replace("network_", "")
    lang = await _get_user_lang(callback.from_user.id)

    await state.update_data(network=network)

    await callback.message.edit_text(
        locale_service.get('enter_amount', lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER),
        reply_markup=preset_amounts_keyboard(lang)
    )

    await state.set_state(OrderStates.waiting_amount)
    await callback.answer()


@router.callback_query(OrderStates.waiting_amount, F.data.startswith("amount_preset_"))
async def enter_amount_preset(callback: CallbackQuery, state: FSMContext):
    """Handle preset amount selection."""
    amount = float(callback.data.replace("amount_preset_", ""))
    lang = await _get_user_lang(callback.from_user.id)

    allowed, _ = global_rate_limiter.check(callback.from_user.id, 'order_amount')
    if not allowed:
        await callback.answer()
        return

    if amount < Config.MIN_ORDER or amount > Config.MAX_ORDER:
        await callback.answer(
            f"❌ المبلغ خارج الحدود ({Config.MIN_ORDER}-{Config.MAX_ORDER} USDT)",
            show_alert=True
        )
        await callback.message.edit_text(
            locale_service.get('enter_amount', lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER),
            reply_markup=preset_amounts_keyboard(lang)
        )
        return

    await callback.message.delete()
    await _process_valid_amount(callback.message, state, lang, amount)
    await callback.answer()


async def _process_valid_amount(message: Message, state: FSMContext, lang: str, amount: float):
    """Continue order flow after amount is validated."""
    # Check daily limit
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", message.from_user.id
        )
        if user:
            today_total = await conn.fetchval(
                "SELECT COALESCE(SUM(amount_usdt), 0) FROM orders "
                "WHERE user_id = $1 AND created_at >= CURRENT_DATE",
                user['id']
            )
            if today_total + amount > Config.DAILY_LIMIT:
                await message.answer(
                    f"❌ تجاوز الحد اليومي!\n"
                    f"الحد اليومي: {Config.DAILY_LIMIT} USDT\n"
                    f"المستخدم اليوم: {today_total:.1f} USDT\n"
                    f"المبلغ المطلوب: {amount} USDT\n"
                    f"المتبقي: {Config.DAILY_LIMIT - today_total:.1f} USDT"
                )
                return False

    await state.update_data(amount_usdt=amount)

    data = await state.get_data()
    network = data['network']

    # Check for saved addresses for this network
    pool = await get_pool()
    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", message.from_user.id
        )
        if user_row:
            saved = await conn.fetch(
                "SELECT id, address, network, label FROM saved_addresses "
                "WHERE user_id = $1 AND network = $2 ORDER BY created_at DESC",
                user_row['id'], network
            )
        else:
            saved = []

    if saved:
        # Show saved addresses first + manual entry option
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        buttons = []
        for addr in saved:
            label = addr.get('label', '') or ''
            full = addr['address']
            short_addr = f"<b>{full[:6]}</b>...<b>{full[-4:]}</b>"
            display = f"{label} - {short_addr}" if label else short_addr
            buttons.append([
                InlineKeyboardButton(text=f"📍 {label}: {full[:6]}...{full[-4:]}" if label else f"📍 {full[:6]}...{full[-4:]}", callback_data=f"order_use_saved_{addr['id']}")
            ])
        manual_text = "✏️ إدخال عنوان جديد" if lang == 'ar' else "✏️ Enter New Address"
        buttons.append([InlineKeyboardButton(text=manual_text, callback_data="order_wallet_manual")])
        await message.answer(
            f"📍 <b>" + ("العناوين المحفوظة" if lang == 'ar' else "Saved Addresses") + f"</b> ({network})\n\n"
            + ("اختر عنواناً أو أدخل عنواناً جديداً:" if lang == 'ar' else "Select an address or enter a new one:"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode='HTML'
        )
    else:
        # No saved addresses — go straight to manual entry
        example = locale_service.get('bep20_example' if network == 'BEP20' else 'trc20_example', lang)
        await message.answer(
            locale_service.get('enter_wallet', lang, network=network, example=example),
            reply_markup=cancel_keyboard(lang),
            parse_mode='HTML'
        )
        await state.set_state(OrderStates.waiting_wallet)

    return True


@router.callback_query(OrderStates.waiting_amount, F.data == "amount_custom")
async def enter_amount_custom(callback: CallbackQuery, state: FSMContext):
    """Let user type custom amount."""
    lang = await _get_user_lang(callback.from_user.id)
    from keyboards.inline import cancel_keyboard
    await callback.message.edit_text(
        locale_service.get('enter_amount_custom', lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER),
        reply_markup=cancel_keyboard(lang)
    )
    await callback.answer()


@router.message(OrderStates.waiting_amount)
async def enter_amount(message: Message, state: FSMContext):
    """Handle amount input."""
    allowed, _ = global_rate_limiter.check(message.from_user.id, 'order_amount')
    if not allowed:
        return

    lang = await _get_user_lang(message.from_user.id)

    try:
        # Strip commas and whitespace before parsing
        amount = float(message.text.strip().replace(',', ''))

        if amount < Config.MIN_ORDER or amount > Config.MAX_ORDER:
            await message.answer(
                locale_service.get('invalid_amount', lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER)
            )
            return

        await _process_valid_amount(message, state, lang, amount)

    except ValueError:
        await message.answer(
            locale_service.get('invalid_amount', lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER)
        )


@router.callback_query(F.data.startswith("order_use_saved_"))
async def use_saved_address_for_order(callback: CallbackQuery, state: FSMContext):
    """Use a saved address during order creation."""
    addr_id = int(callback.data.replace("order_use_saved_", ""))
    pool = await get_pool()
    lang = await _get_user_lang(callback.from_user.id)

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id
        )
        if user:
            addr = await conn.fetchrow(
                "SELECT address, network FROM saved_addresses WHERE id = $1 AND user_id = $2",
                addr_id, user['id']
            )
        else:
            addr = None

    if not addr:
        await callback.answer("❌ العنوان غير موجود", show_alert=True)
        return

    await state.update_data(wallet_address=addr['address'])

    await callback.message.edit_text(
        f"✅ " + ("تم استخدام العنوان المحفوظ!" if lang == 'ar' else "Saved address selected!") + f"\n\n"
        f"📍 <code>{addr['address']}</code>\n"
        f"🌐 {addr['network']}"
    )

    # Continue to QR prompt (skip wallet validation — already saved/verified)
    qr_prompt = "📸 <b>هل تريد إرفاق رمز QR لعنوان محفظتك؟</b>\n\n" \
                "يمكنك إرسال صورة QR ليسهل على الأدمن إرسال USDT.\n" \
                "أرسل صورة QR، أو اضغط 'تخطي' للمتابعة." if lang == 'ar' else \
                "📸 <b>Would you like to attach a QR code of your wallet address?</b>\n\n" \
                "Send a QR image to help the admin send USDT.\n" \
                "Send a QR image, or click 'Skip' to continue."
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    qr_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ تخطي" if lang == 'ar' else "⏭️ Skip", callback_data="skip_wallet_qr")]
    ])
    await callback.message.answer(qr_prompt, reply_markup=qr_keyboard, parse_mode='HTML')
    await state.set_state(OrderStates.waiting_wallet_qr)
    await callback.answer()


@router.callback_query(F.data == "order_wallet_manual")
async def enter_wallet_manual(callback: CallbackQuery, state: FSMContext):
    """User chose manual wallet entry instead of saved address."""
    lang = await _get_user_lang(callback.from_user.id)
    data = await state.get_data()
    network = data.get('network', 'BEP20')
    example = locale_service.get('bep20_example' if network == 'BEP20' else 'trc20_example', lang)

    await callback.message.edit_text(
        locale_service.get('enter_wallet', lang, network=network, example=example),
        reply_markup=cancel_keyboard(lang),
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.waiting_wallet)
    await callback.answer()


@router.message(OrderStates.waiting_wallet)
async def enter_wallet(message: Message, state: FSMContext):
    """Handle wallet input."""
    allowed, _ = global_rate_limiter.check(message.from_user.id, 'order_wallet')
    if not allowed:
        return

    lang = await _get_user_lang(message.from_user.id)
    # Strip all whitespace including spaces inside the address
    wallet = message.text.replace(' ', '').replace('\t', '').replace('\n', '').strip()

    data = await state.get_data()
    network = data['network']

    # Validate wallet
    validation = WalletValidator.validate(wallet, network)

    if not validation['valid']:
        await message.answer(
            locale_service.get('invalid_wallet', lang, network=network)
        )
        return

    await state.update_data(wallet_address=wallet)

    # Check cross-network
    other_network = WalletValidator.detect_network(wallet)
    if other_network and other_network != network:
        # Offer automatic switch to the corrected network
        switch_text = f"🔄 التبديل إلى {other_network}" if lang == 'ar' else f"🔄 Switch to {other_network}"
        continue_text = "✅ الاستمرار مع " + network if lang == 'ar' else f"✅ Continue with {network}"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        network_switch_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=switch_text, callback_data=f"switch_to_network_{other_network}")],
            [InlineKeyboardButton(text=continue_text, callback_data="skip_network_switch")]
        ])
        await message.answer(
            locale_service.get('wallet_cross_check_switch', lang, other_network=other_network, current_network=network),
            reply_markup=network_switch_keyboard,
            parse_mode='HTML'
        )
        return  # Wait for user to choose

    await message.answer(
        locale_service.get('wallet_valid', lang),
    )

    # Ask if they want to attach a QR code of their wallet address
    qr_prompt = "📸 <b>هل تريد إرفاق رمز QR لعنوان محفظتك؟</b>\n\n" \
                "يمكنك إرسال صورة QR ليسهل على الأدمن إرسال USDT.\n" \
                "أرسل صورة QR، أو اضغط 'تخطي' للمتابعة." if lang == 'ar' else \
                "📸 <b>Would you like to attach a QR code of your wallet address?</b>\n\n" \
                "Send a QR image to help the admin send USDT.\n" \
                "Send a QR image, or click 'Skip' to continue."
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    skip_only_btn = "⏭️ تخطي" if lang == 'ar' else "⏭️ Skip"
    qr_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=skip_only_btn, callback_data="skip_wallet_qr")]
    ])
    await message.answer(qr_prompt, reply_markup=qr_keyboard, parse_mode='HTML')

    await state.set_state(OrderStates.waiting_wallet_qr)


@router.callback_query(OrderStates.waiting_wallet_qr, F.data == "skip_wallet_qr")
async def skip_wallet_qr(callback: CallbackQuery, state: FSMContext):
    """Skip wallet QR code upload."""
    lang = await _get_user_lang(callback.from_user.id)
    data = await state.get_data()
    wallet = data.get('wallet_address', '')
    network = data.get('network', '')

    # Go to save address prompt instead
    save_text = locale_service.get('save_address_prompt', lang, address=wallet, network=network)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    save_btn = "💾 حفظ العنوان" if lang == 'ar' else "💾 Save Address"
    skip_btn = "⏭️ تخطي" if lang == 'ar' else "⏭️ Skip"
    save_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=save_btn, callback_data="save_address_yes"),
         InlineKeyboardButton(text=skip_btn, callback_data="save_address_skip")]
    ])
    await callback.message.edit_text(
        save_text,
        reply_markup=save_keyboard,
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.waiting_save_address)
    await callback.answer()


@router.message(OrderStates.waiting_wallet_qr, F.photo)
async def receive_wallet_qr(message: Message, state: FSMContext):
    """Receive wallet QR code photo from customer."""
    lang = await _get_user_lang(message.from_user.id)
    qr_photo_id = message.photo[-1].file_id

    await state.update_data(wallet_qr_photo_id=qr_photo_id)

    data = await state.get_data()
    wallet = data.get('wallet_address', '')
    network = data.get('network', '')

    await message.answer(
        "✅ تم استلام رمز QR الخاص بمحفظتك!" if lang == 'ar' else "✅ Wallet QR code received!"
    )

    # Go to save address prompt
    save_text = locale_service.get('save_address_prompt', lang, address=wallet, network=network)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    save_btn = "💾 حفظ العنوان" if lang == 'ar' else "💾 Save Address"
    skip_btn = "⏭️ تخطي" if lang == 'ar' else "⏭️ Skip"
    save_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=save_btn, callback_data="save_address_yes"),
         InlineKeyboardButton(text=skip_btn, callback_data="save_address_skip")]
    ])
    await message.answer(save_text, reply_markup=save_keyboard, parse_mode='HTML')

    await state.set_state(OrderStates.waiting_save_address)


@router.message(OrderStates.waiting_wallet_qr, F.text)
async def skip_wallet_qr_text(message: Message, state: FSMContext):
    """Skip wallet QR if user sends text instead of photo."""
    lang = await _get_user_lang(message.from_user.id)
    data = await state.get_data()
    wallet = data.get('wallet_address', '')
    network = data.get('network', '')

    await message.answer(
        "✅ سيتم المتابعة بدون رمز QR." if lang == 'ar' else "✅ Continuing without QR code."
    )

    # Go to save address prompt
    save_text = locale_service.get('save_address_prompt', lang, address=wallet, network=network)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    save_btn = "💾 حفظ العنوان" if lang == 'ar' else "💾 Save Address"
    skip_btn = "⏭️ تخطي" if lang == 'ar' else "⏭️ Skip"
    save_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=save_btn, callback_data="save_address_yes"),
         InlineKeyboardButton(text=skip_btn, callback_data="save_address_skip")]
    ])
    await message.answer(save_text, reply_markup=save_keyboard, parse_mode='HTML')

    await state.set_state(OrderStates.waiting_save_address)


@router.callback_query(F.data.startswith("switch_to_network_"))
async def switch_to_network_corrected(callback: CallbackQuery, state: FSMContext):
    """User clicked to switch to the corrected network after cross-network detection."""
    target_network = callback.data.replace("switch_to_network_", "")
    lang = await _get_user_lang(callback.from_user.id)

    # Update state with the corrected network (keep wallet address)
    await state.update_data(network=target_network)

    data = await state.get_data()
    wallet = data.get('wallet_address', '')

    await callback.message.edit_text(
        f"🔄 تم التبديل إلى <b>{target_network}</b> ✓" if lang == 'ar' else
        f"🔄 Switched to <b>{target_network}</b> ✓",
        parse_mode='HTML'
    )

    # Re-validate wallet with new network
    validation = WalletValidator.validate(wallet, target_network)
    if validation['valid']:
        await callback.message.answer(
            locale_service.get('wallet_valid', lang),
        )
        # Ask for QR code (continue the flow from after wallet validation)
        qr_prompt = "📸 <b>هل تريد إرفاق رمز QR لعنوان محفظتك؟</b>\n\n" \
                    "يمكنك إرسال صورة QR ليسهل على الأدمن إرسال USDT.\n" \
                    "أرسل صورة QR، أو اضغط 'تخطي' للمتابعة." if lang == 'ar' else \
                    "📸 <b>Would you like to attach a QR code of your wallet address?</b>\n\n" \
                    "Send a QR image to help the admin send USDT.\n" \
                    "Send a QR image, or click 'Skip' to continue."
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        qr_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ تخطي" if lang == 'ar' else "⏭️ Skip", callback_data="skip_wallet_qr")]
        ])
        await callback.message.answer(qr_prompt, reply_markup=qr_keyboard, parse_mode='HTML')
        await state.set_state(OrderStates.waiting_wallet_qr)
    else:
        # Wallet invalid on new network - go back to enter_wallet
        await callback.message.answer(
            f"❌ المحفظة غير صالحة على {target_network}. أعد إدخال عنوان صحيح." if lang == 'ar' else
            f"❌ Wallet invalid on {target_network}. Please re-enter a valid address.",
        )
        network = data.get('network', 'BEP20')
        example = locale_service.get('bep20_example' if network == 'BEP20' else 'trc20_example', lang)
        await callback.message.answer(
            locale_service.get('enter_wallet', lang, network=network, example=example),
            reply_markup=cancel_keyboard(lang)
        )
        await state.set_state(OrderStates.waiting_wallet)


@router.callback_query(F.data == "skip_network_switch")
async def skip_network_switch(callback: CallbackQuery, state: FSMContext):
    """User chose to keep the original network despite cross-network warning."""
    lang = await _get_user_lang(callback.from_user.id)
    data = await state.get_data()
    wallet = data.get('wallet_address', '')

    await callback.message.edit_text(
        "✅ تم الاستمرار مع الشبكة المحددة." if lang == 'ar' else "✅ Continuing with selected network."
    )

    await callback.message.answer(
        locale_service.get('wallet_valid', lang),
    )

    # Continue to QR prompt
    qr_prompt = "📸 <b>هل تريد إرفاق رمز QR لعنوان محفظتك؟</b>\n\n" \
                "يمكنك إرسال صورة QR ليسهل على الأدمن إرسال USDT.\n" \
                "أرسل صورة QR، أو اضغط 'تخطي' للمتابعة." if lang == 'ar' else \
                "📸 <b>Would you like to attach a QR code of your wallet address?</b>\n\n" \
                "Send a QR image to help the admin send USDT.\n" \
                "Send a QR image, or click 'Skip' to continue."
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    qr_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ تخطي" if lang == 'ar' else "⏭️ Skip", callback_data="skip_wallet_qr")]
    ])
    await callback.message.answer(qr_prompt, reply_markup=qr_keyboard, parse_mode='HTML')
    await state.set_state(OrderStates.waiting_wallet_qr)
    await callback.answer()


@router.callback_query(OrderStates.waiting_currency, F.data.startswith("currency_"))
async def select_currency(callback: CallbackQuery, state: FSMContext):
    """Handle currency selection."""
    currency = callback.data.replace("currency_", "")
    lang = await _get_user_lang(callback.from_user.id)

    await state.update_data(payment_currency=currency)

    data = await state.get_data()

    # Calculate order
    pool = await get_pool()
    exchange = ExchangeService(pool)

    calculation = await exchange.calculate_order(
        data['amount_usdt'],
        currency
    )

    await state.update_data(calculation=calculation)

    # Build new Syrian Lira lines if SYP
    new_syr_line = ""
    new_syr_fee_line = ""
    new_syr_total_line = ""
    if currency == 'SYP':
        new_syr_line = f"🇸🇾 بما يعادل: <b>{calculation['new_syr_amount']:,.2f} ل.ج.س</b> (ليرة جديدة سورية)\n"
        new_syr_fee_line = f"🇸🇾 بما يعادل: <b>{calculation['new_syr_fee']:,.2f} ل.ج.س</b>\n"
        new_syr_total_line = f"🇸🇾 الإجمالي بل.ج.س: <b>{calculation['new_syr_total']:,.2f} ل.ج.س</b>\n"

    # Show summary
    summary = locale_service.get(
        'order_summary',
        lang,
        order_number="PENDING",
        amount_usdt=data['amount_usdt'],
        network=data['network'],
        wallet=data['wallet_address'],
        currency=currency,
        rate=calculation['exchange_rate'],
        base_amount=calculation['base_amount'],
        fee_percent=calculation['fee_percent'],
        fee_amount=calculation['fee_amount'],
        total=calculation['total_amount'],
        new_syr_line=new_syr_line,
        new_syr_fee_line=new_syr_fee_line,
        new_syr_total_line=new_syr_total_line
    )

    await callback.message.edit_text(summary, parse_mode='HTML')
    await callback.message.answer(
        locale_service.get('confirm_order', lang),
        reply_markup=order_confirmation_keyboard(lang)
    )

    await state.set_state(OrderStates.waiting_confirmation)
    await callback.answer()


@router.callback_query(OrderStates.waiting_confirmation, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    """Confirm and create order."""
    allowed, _ = global_rate_limiter.check(callback.from_user.id, 'order_confirm')
    if not allowed:
        await callback.answer()
        return

    lang = await _get_user_lang(callback.from_user.id)

    data = await state.get_data()
    calculation = data['calculation']

    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            callback.from_user.id
        )

        order_number = generate_order_number()

        wallet_qr = data.get('wallet_qr_photo_id', None)
        row = await conn.fetchrow("""
            INSERT INTO orders (
                order_number, user_id, network, amount_usdt, exchange_rate,
                payment_currency, base_amount, fee_percent, fee_amount,
                total_amount, wallet_address, wallet_qr_photo_id, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'pending')
            RETURNING id
        """,
            order_number, user['id'], data['network'], data['amount_usdt'],
            calculation['exchange_rate'], data['payment_currency'],
            calculation['base_amount'], calculation['fee_percent'],
            calculation['fee_amount'], calculation['total_amount'],
            data['wallet_address'], wallet_qr
        )
        order_id = row['id']

    # Notify admins with full customer info and delivery address
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)

    # Get customer full name from DB
    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT full_name FROM users WHERE id = $1", user['id']
        )
    customer_name = user_row['full_name'] if user_row else 'N/A'

    admin_text = (
        f"📦 <b>طلب جديد!</b>\n\n"
        f"📋 الرقم: #{order_number}\n"
        f"👤 الاسم: {customer_name}\n"
        f"🆔 المعرف: <code>{callback.from_user.id}</code>\n"
        f"👤 المستخدم: @{callback.from_user.username or 'N/A'}\n"
        f"💰 المبلغ: {data['amount_usdt']} USDT\n"
        f"🌐 الشبكة: {data['network']}\n"
        f"💱 العملة: {data['payment_currency']}\n"
        f"💵 الإجمالي (شامل الرسوم): {calculation['total_amount']:.2f} {data['payment_currency']}\n"
        f"📍 <b>عنوان التسليم:</b> <code>{data['wallet_address']}</code>\n"
    )
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=order_admin_keyboard(order_id, 'pending'),
                parse_mode='HTML'
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to notify admin {admin_id}: {e}")

    await callback.message.edit_text(
        locale_service.get('order_created', lang, order_number=order_number),
        parse_mode='HTML'
    )

    await callback.message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )

    await state.clear()
    await callback.answer()


@router.callback_query(OrderStates.waiting_save_address, F.data == "save_address_yes")
async def save_address_yes(callback: CallbackQuery, state: FSMContext):
    """Save wallet address and proceed to currency selection."""
    lang = await _get_user_lang(callback.from_user.id)
    data = await state.get_data()
    wallet = data.get('wallet_address', '')
    network = data.get('network', '')

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id
        )
        if user:
            await conn.execute(
                "INSERT INTO saved_addresses (user_id, address, network) VALUES ($1, $2, $3)",
                user['id'], wallet, network
            )

    await callback.message.edit_text(
        locale_service.get('address_saved', lang),
    )

    # Proceed to currency selection
    await callback.message.answer(
        locale_service.get('select_currency', lang),
        reply_markup=currency_selection_keyboard(lang)
    )

    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()


@router.callback_query(OrderStates.waiting_save_address, F.data == "save_address_skip")
async def save_address_skip(callback: CallbackQuery, state: FSMContext):
    """Skip saving address and proceed to currency selection."""
    lang = await _get_user_lang(callback.from_user.id)

    await callback.message.edit_text(
        locale_service.get('wallet_valid', lang),
    )

    await callback.message.answer(
        locale_service.get('select_currency', lang),
        reply_markup=currency_selection_keyboard(lang)
    )

    await state.set_state(OrderStates.waiting_currency)
    await callback.answer()
