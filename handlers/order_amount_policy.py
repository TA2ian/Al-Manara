"""Authoritative amount-entry policy for customer orders."""
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from database import get_pool
from keyboards.inline import cancel_keyboard, preset_amounts_keyboard, start_verification_keyboard
from middleware.rate_limit import rate_limiter as global_rate_limiter
from services.formatters import usdt
from services.locale_service import locale_service
from states import OrderStates, WalletStates

router = Router()
ACTIVE_STATUSES = ("pending", "waiting_payment", "receipt_received", "payment_confirmed")


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
            user_id, ACTIVE_STATUSES,
        )


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
        buttons = []
        for row in rows:
            label = row["label"] or ("بدون اسم" if lang == "ar" else "Unnamed")
            icon = "🔷" if row["network"] == "TRC20" else "🟡"
            buttons.append([InlineKeyboardButton(text=f"{icon} {label} · {row['address'][:6]}...{row['address'][-4:]}", callback_data=f"order_use_saved_{row['id']}")])
        buttons.append([InlineKeyboardButton(text="➕ إضافة محفظة جديدة" if lang == "ar" else "➕ Add a new wallet", callback_data="order_wallet_manual")])
        buttons.append([InlineKeyboardButton(text="❌ إلغاء الطلب" if lang == "ar" else "❌ Cancel order", callback_data="cancel_order")])
        await message.answer(
            "👛 <b>اختر محفظة موثقة</b>\n\nسيتم استخدام QR المحفوظ تلقائياً لهذا الطلب." if lang == "ar" else
            "👛 <b>Select a verified wallet</b>\n\nIts stored QR will be reused automatically for this order.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML",
        )
        return
    await state.update_data(return_to_order=True)
    await state.set_state(WalletStates.waiting_address)
    await message.answer(
        "👛 <b>إضافة محفظة للاستلام</b>\n\nلا توجد محفظة موثقة بعد. أرسل عنوان BEP20 أو TRC20. بعد التحقق سنطلب QR المطابق مرة واحدة فقط." if lang == "ar" else
        "👛 <b>Add a receiving wallet</b>\n\nNo verified wallet is available yet. Send a BEP20 or TRC20 address. After validation, we will request the matching QR once.",
        reply_markup=cancel_keyboard(lang), parse_mode="HTML",
    )


@router.message(F.text.in_(["💰 جديد", "💰 New", "💰 إنشاء طلب شراء", "💰 Buy Order"]))
async def start_order_authoritative(message: Message, state: FSMContext):
    """Start a new order through the authoritative customer gates."""
    user = await _user(message.from_user.id)
    if not user:
        await message.answer("يرجى بدء البوت أولاً: /start")
        return
    lang = user["language"] or "ar"
    if not user["terms_accepted"]:
        await message.answer("يرجى قبول الشروط أولاً: /start" if lang == "ar" else "Please accept the terms first: /start")
        return
    if user["is_blocked"]:
        await message.answer(locale_service.get("user_blocked", lang), parse_mode="HTML")
        return
    if not user["is_verified"]:
        await message.answer(
            "🔒 <b>يرجى إكمال التوثيق أولاً</b>\n\nلإنشاء طلب، يجب توثيق حسابك أولاً." if lang == "ar" else
            "🔒 <b>Verification required</b>\n\nYou must verify your account before creating an order.",
            parse_mode="HTML", reply_markup=start_verification_keyboard(lang),
        )
        return
    active = await _active_order(user["id"])
    if active:
        await message.answer(
            "⚠️ <b>لديك طلب نشط بالفعل.</b> افتح طلباتي لمتابعته ولا يمكنك إنشاء طلب جديد قبل اكتماله." if lang == "ar" else
            "⚠️ <b>You already have an active order.</b> Open Orders to follow it; a new order cannot be created until it is completed.",
            parse_mode="HTML",
        )
        return

    await state.clear()
    await state.set_state(OrderStates.waiting_amount)
    await message.answer(locale_service.get("enter_amount", lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER), reply_markup=preset_amounts_keyboard(lang))


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
        await message.answer(
            "⚠️ <b>لديك طلب نشط بالفعل.</b> افتح طلباتي لمتابعته ولا يمكنك إنشاء طلب جديد قبل اكتماله." if lang == "ar" else
            "⚠️ <b>You already have an active order</b> Open Orders to follow it; a new order cannot be created until it is completed.",
            parse_mode="HTML",
        )
        await state.clear()
        return
    if amount < Config.MIN_ORDER or amount > Config.MAX_ORDER:
        await message.answer(locale_service.get("invalid_amount", lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER))
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        today_total = await conn.fetchval("SELECT COALESCE(SUM(amount_usdt), 0) FROM orders WHERE user_id = $1 AND created_at >= CURRENT_DATE", user["id"])
    if Decimal(str(today_total or 0)) + amount > Decimal(str(Config.DAILY_LIMIT)):
        remaining = Decimal(str(Config.DAILY_LIMIT)) - Decimal(str(today_total or 0))
        await message.answer(
            f"❌ تجاوز الحد اليومي.\nالحد اليومي: {usdt(Config.DAILY_LIMIT)} USDT\nالمستخدم اليوم: {usdt(today_total)} USDT\nالمبلغ المطلوب: {usdt(amount)} USDT\nالمتبقي: {usdt(max(remaining, Decimal('0')))} USDT" if lang == "ar" else
            f"❌ The daily limit would be exceeded.\nDaily limit: {usdt(Config.DAILY_LIMIT)} USDT\nUsed today: {usdt(today_total)} USDT\nRequested: {usdt(amount)} USDT\nRemaining: {usdt(max(remaining, Decimal('0')))} USDT"
        )
        return
    await state.update_data(amount_usdt=amount, order_amount_usdt=amount)
    await _show_verified_wallets(message, state, user["id"], lang)


@router.callback_query(OrderStates.waiting_amount, F.data.startswith("amount_preset_"))
async def enter_amount_preset(callback: CallbackQuery, state: FSMContext):
    try:
        amount = Decimal(callback.data.removeprefix("amount_preset_"))
    except InvalidOperation:
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
    await callback.message.edit_text(locale_service.get("enter_amount_custom", lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER), reply_markup=cancel_keyboard(lang))
    await callback.answer()


@router.message(OrderStates.waiting_amount)
async def enter_amount(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] if user else "ar") or "ar"
    try:
        amount = Decimal((message.text or "").strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        await message.answer(locale_service.get("invalid_amount", lang, min=Config.MIN_ORDER, max=Config.MAX_ORDER))
        return
    await _accept_amount(message, state, amount, lang, message.from_user.id)
