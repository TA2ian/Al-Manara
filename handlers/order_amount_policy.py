"""Authoritative amount-entry policy for customer orders."""
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from database import get_pool
from keyboards.inline import cancel_keyboard, currency_selection_keyboard, preset_amounts_keyboard, start_verification_keyboard
from keyboards.reply import remove_dashboard_keyboard
from middleware.rate_limit import rate_limiter as global_rate_limiter
from services.formatters import usdt
from services.locale_service import locale_service
from services.operational_policy_service import OperationalPolicyService
from services.order_lifecycle import ACTIVE_ORDER_STATUSES
from states import OrderStates, WalletStates

router = Router()


async def _user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, language, terms_accepted, is_blocked, is_verified FROM users WHERE telegram_id = $1",
            telegram_id,
        )


async def _active_order(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT order_number, amount_usdt, status FROM orders WHERE user_id = $1 AND status = ANY($2) ORDER BY created_at DESC LIMIT 1",
            user_id, list(ACTIVE_ORDER_STATUSES),
        )


def _wallet_choice_keyboard(rows, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    icons = {"BEP20": "🟡", "TRC20": "🔷", "TON": "💎", "ARB": "🔵", "SOLANA": "🟣", "ETH": "⚪"}
    for row in rows:
        label = row["label"] or ("بدون اسم" if lang == "ar" else "Unnamed")
        icon = icons.get(row["network"], "🌐")
        buttons.append([InlineKeyboardButton(text=f"{icon} {label} · {row['address'][:6]}...{row['address'][-4:]}", callback_data=f"order_use_saved_{row['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ إضافة محفظة جديدة" if lang == "ar" else "➕ Add a new wallet", callback_data="order_wallet_manual")])
    buttons.append([InlineKeyboardButton(text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order", callback_data="cancel_order")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_verified_wallets(message: Message, state: FSMContext, user_id: int, lang: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, address, network, label FROM saved_addresses
               WHERE user_id = $1 AND deleted_at IS NULL
                 AND verification_status = 'verified' AND qr_photo_id IS NOT NULL
               ORDER BY is_default DESC, created_at DESC""", user_id,
        )
    if rows:
        await message.answer(
            "👛 <b>اختر محفظة موثقة</b>\n\nسيتم استخدام QR المحفوظ تلقائياً لهذا الطلب." if lang == "ar" else
            "👛 <b>Select a verified wallet</b>\n\nIts stored QR will be reused automatically for this order.",
            reply_markup=_wallet_choice_keyboard(rows, lang), parse_mode="HTML",
        )
        await state.set_state(OrderStates.waiting_wallet)
        return
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_network)
    from keyboards.wallet import wallet_network_keyboard
    await message.answer(
        "👛 <b>إضافة محفظة للاستلام</b>\n\nاختر شبكة USDT أولاً، ثم أرسل العنوان أو QR أو شارك المحفظة مباشرة من تطبيق محفظتك." if lang == "ar" else
        "👛 <b>Add a receiving wallet</b>\n\nSelect the USDT network first, then send the address, QR, or share the wallet directly from your wallet app.",
        reply_markup=wallet_network_keyboard(lang, cancel_callback="cancel_order"), parse_mode="HTML",
    )


@router.message(F.text.in_(["💰 新", "💰 جديد", "💰 New", "💰 إنشاء طلب شراء", "💰 Buy Order"]))
async def start_order_authoritative(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    if not user:
        await message.answer("يرجى بدء البوت أولاً: /start")
        return
    lang = user["language"] or "ar"
    if not user["terms_accepted"]:
        await message.answer("يرجى قبول الشروط أولاً: /start" if lang == "ar" else "Please accept the terms first: /start")
        return
    if user["is_blocked"]:
        await message.answer("⛔ الحساب محظور." if lang == "ar" else "⛔ Your account is blocked.")
        return
    if not user["is_verified"]:
        await message.answer("🔒 <b>يرجى إكمال التوثيق أولاً</b>\n\nلإنشاء طلب، يجب توثيق حسابك أولاً." if lang == "ar" else "🔒 <b>Verification required</b>\n\nYou must verify your account before creating an order.", parse_mode="HTML", reply_markup=start_verification_keyboard(lang))
        return
    active = await _active_order(user["id"])
    if active:
        await message.answer("⚠️ <b>لديك طلب نشط بالفعل.</b> افتح طلباتي لمتابعته ولا يمكنك إنشاء طلب جديد قبل اكتماله." if lang == "ar" else "⚠️ <b>You already have an active order.</b> Open Orders to follow it.", parse_mode="HTML")
        return
    limits = await OperationalPolicyService.get_limits()
    await state.clear()
    await state.set_state(OrderStates.waiting_amount)
    await message.answer("🔄", reply_markup=remove_dashboard_keyboard())
    await message.answer(locale_service.get("enter_amount", lang, min=limits["min_order"], max=limits["max_order"]) + ("\n\nℹ️ المبلغ الذي تحدده هو إجمالي القيمة التي تريد دفعها؛ رسوم الشبكة تُخصم منه ولا تُضاف فوقه." if lang == "ar" else "\n\nℹ️ The amount you enter is the gross value you want to pay; the network fee is deducted from it, not added on top."), reply_markup=preset_amounts_keyboard(lang))


async def _accept_amount(message: Message, state: FSMContext, amount: Decimal, lang: str, user_id: int):
    allowed, _ = global_rate_limiter.check(user_id, "order_amount")
    if not allowed:
        return
    user = await _user(user_id)
    if not user:
        await message.answer("يرجى بدء البوت أولاً: /start" if lang == "ar" else "Please start the bot first: /start")
        return
    active = await _active_order(user["id"])
    if active:
        await message.answer("⚠️ لديك طلب نشط بالفعل. افتح طلباتي لمتابعته." if lang == "ar" else "⚠️ You already have an active order. Open Orders.")
        await state.clear()
        return
    limits = await OperationalPolicyService.get_limits()
    minimum, maximum, daily_limit = limits["min_order"], limits["max_order"], limits["daily_limit"]
    if amount < minimum or amount > maximum:
        await message.answer(locale_service.get("invalid_amount", lang, min=minimum, max=maximum))
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        today_total = await conn.fetchval("SELECT COALESCE(SUM(COALESCE(requested_amount_usdt, amount_usdt)), 0) FROM orders WHERE user_id = $1 AND created_at >= CURRENT_DATE", user["id"])
    if Decimal(str(today_total or 0)) + amount > daily_limit:
        remaining = daily_limit - Decimal(str(today_total or 0))
        await message.answer(
            f"❌ تجاوز الحد اليومي.\nالحد اليومي: {usdt(daily_limit)} USDT\nالمستخدم اليوم: {usdt(today_total)} USDT\nالمبلغ المطلوب: {usdt(amount)} USDT\nالمتبقي: {usdt(max(remaining, Decimal('0')))} USDT" if lang == "ar" else
            f"❌ The daily limit would be exceeded.\nDaily limit: {usdt(daily_limit)} USDT\nUsed today: {usdt(today_total)} USDT\nRequested: {usdt(amount)} USDT\nRemaining: {usdt(max(remaining, Decimal('0')))} USDT"
        )
        return
    await state.update_data(amount_usdt=amount, order_amount_usdt=amount, requested_amount_usdt=amount)
    await _show_verified_wallets(message, state, user["id"], lang)


@router.callback_query(OrderStates.waiting_amount, F.data.startswith("amount_preset_"))
async def enter_amount_preset(callback: CallbackQuery, state: FSMContext):
    try:
        amount = Decimal(callback.data.removeprefix("amount_preset_"))
    except (InvalidOperation, ValueError):
        await callback.answer("❌ Invalid amount", show_alert=True)
        return
    user = await _user(callback.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"
    await _accept_amount(callback.message, state, amount, lang, callback.from_user.id)
    await callback.answer()


@router.callback_query(OrderStates.waiting_amount, F.data == "amount_custom")
async def enter_amount_custom(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"
    limits = await OperationalPolicyService.get_limits()
    await callback.message.edit_text(locale_service.get("enter_amount_custom", lang, min=limits["min_order"], max=limits["max_order"]), reply_markup=cancel_keyboard(lang))
    await callback.answer()


@router.message(OrderStates.waiting_amount)
async def enter_amount(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"
    try:
        amount = Decimal((message.text or "").strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        limits = await OperationalPolicyService.get_limits()
        await message.answer(locale_service.get("invalid_amount", lang, min=limits["min_order"], max=limits["max_order"]))
        return
    await _accept_amount(message, state, amount, lang, message.from_user.id)


async def resume_order_after_wallet(message: Message, state: FSMContext, wallet_id: int):
    """Resume the canonical order flow after a wallet has been saved."""
    user = await _user(message.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"
    data = await state.get_data()
    await state.update_data(wallet_id=wallet_id, return_to_order=True)
    await state.set_state(OrderStates.waiting_currency)
    await message.answer(locale_service.get("select_currency", lang), reply_markup=currency_selection_keyboard(lang))
