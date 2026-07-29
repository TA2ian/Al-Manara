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
    order_admin_keyboard
)
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from services.wallet_validator import WalletValidator
from services.exchange_service import ExchangeService
from services.notification_service import NotificationService
from config import Config
from database import get_pool
from keyboards.inline import start_verification_keyboard

router = Router()


def generate_order_number() -> str:
    """Generate unique order number."""
    return f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


@router.message(F.text.in_(["💰 جديد", "💰 New"]))
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
        reply_markup=network_selection_keyboard(lang)
    )

    await state.set_state(OrderStates.waiting_network)


@router.callback_query(OrderStates.waiting_network, F.data.startswith("network_"))
async def select_network(callback: CallbackQuery, state: FSMContext):
    """Handle network selection."""
    network = callback.data.replace("network_", "")
    lang = 'ar'  # Get from user

    await state.update_data(network=network)

    await callback.message.edit_text(
        locale_service.get('enter_amount', lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER),
        reply_markup=cancel_keyboard(lang)
    )

    await state.set_state(OrderStates.waiting_amount)
    await callback.answer()


@router.message(OrderStates.waiting_amount)
async def enter_amount(message: Message, state: FSMContext):
    """Handle amount input."""
    lang = 'ar'  # Get from user

    try:
        amount = float(message.text.strip())

        if amount < Config.MIN_ORDER or amount > Config.MAX_ORDER:
            await message.answer(
                locale_service.get('invalid_amount', lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER)
            )
            return

        await state.update_data(amount_usdt=amount)

        data = await state.get_data()
        network = data['network']

        example = locale_service.get('bep20_example' if network == 'BEP20' else 'trc20_example', lang)

        await message.answer(
            locale_service.get('enter_wallet', lang, network=network, example=example),
            reply_markup=cancel_keyboard(lang)
        )

        await state.set_state(OrderStates.waiting_wallet)

    except ValueError:
        await message.answer(
            locale_service.get('invalid_amount', lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER)
        )


@router.message(OrderStates.waiting_wallet)
async def enter_wallet(message: Message, state: FSMContext):
    """Handle wallet input."""
    lang = 'ar'  # Get from user
    wallet = message.text.strip()

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
        await message.answer(
            locale_service.get('wallet_cross_check', lang, other_network=other_network)
        )

    await message.answer(
        locale_service.get('wallet_valid', lang),
        reply_markup=currency_selection_keyboard(lang)
    )

    await state.set_state(OrderStates.waiting_currency)


@router.callback_query(OrderStates.waiting_currency, F.data.startswith("currency_"))
async def select_currency(callback: CallbackQuery, state: FSMContext):
    """Handle currency selection."""
    currency = callback.data.replace("currency_", "")
    lang = 'ar'  # Get from user

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
        total=calculation['total_amount']
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
    lang = 'ar'  # Get from user

    data = await state.get_data()
    calculation = data['calculation']

    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            callback.from_user.id
        )

        order_number = generate_order_number()

        row = await conn.fetchrow("""
            INSERT INTO orders (
                order_number, user_id, network, amount_usdt, exchange_rate,
                payment_currency, base_amount, fee_percent, fee_amount,
                total_amount, wallet_address, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'pending')
            RETURNING id
        """,
            order_number, user['id'], data['network'], data['amount_usdt'],
            calculation['exchange_rate'], data['payment_currency'],
            calculation['base_amount'], calculation['fee_percent'],
            calculation['fee_amount'], calculation['total_amount'],
            data['wallet_address']
        )
        order_id = row['id']

    # Notify admins with action buttons
    from aiogram import Bot
    bot = Bot(token=Config.BOT_TOKEN)
    admin_text = (
        f"📦 <b>طلب جديد!</b>\n\n"
        f"📋 الرقم: #{order_number}\n"
        f"👤 العميل: @{callback.from_user.username or 'N/A'}\n"
        f"💰 المبلغ: {data['amount_usdt']} USDT\n"
        f"🌐 الشبكة: {data['network']}\n"
        f"💱 العملة: {data['payment_currency']}\n"
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
