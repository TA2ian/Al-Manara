"""Customer-facing language guard for order entry edge cases."""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database import get_pool
from keyboards.inline import start_verification_keyboard
from services.locale_service import locale_service

router = Router()

BUY_ORDER_TEXTS = {"💰 جديد", "💰 New", "💰 إنشاء طلب شراء", "💰 Buy Order"}


@router.message(F.text.in_(BUY_ORDER_TEXTS))
async def guard_unverified_order(message: Message, state: FSMContext):
    """Handle unverified users before legacy order text handlers can emit Arabic-only text."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT terms_accepted, is_blocked, is_verified, language FROM users WHERE telegram_id=$1",
            message.from_user.id,
        )

    if not user:
        lang = "ar"
        await message.answer(
            "❌ الرجاء البدء أولاً: /start" if lang == "ar" else "❌ Please start the bot first: /start"
        )
        return

    lang = user["language"] if user["language"] in ("ar", "en") else "ar"

    if not user["terms_accepted"]:
        await message.answer(
            "❗ يرجى قبول الشروط أولاً عبر /start."
            if lang == "ar" else
            "❗ Please accept the terms first by using /start."
        )
        return

    if user["is_blocked"]:
        await message.answer(locale_service.get("user_blocked", lang), parse_mode="HTML")
        return

    if user["is_verified"]:
        # Do not consume the event for verified users; active_order_policy/order
        # handlers below must continue to handle the normal order flow.
        return

    await message.answer(
        "🔒 <b>يجب إكمال توثيق الحساب أولاً</b>\n\n"
        "قبل إنشاء طلب شراء، أكمل التوثيق بإدخال رقم هاتفك، اسمك الكامل، رقم حساب ShamCash (عنوان الاستلام)، وصورة QR للحساب."
        if lang == "ar" else
        "🔒 <b>Account verification is required first</b>\n\n"
        "Before creating a buy order, complete verification with your phone number, full name, ShamCash account number (receiving address), and account QR image.",
        parse_mode="HTML",
        reply_markup=start_verification_keyboard(lang),
    )
