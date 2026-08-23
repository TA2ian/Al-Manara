"""Authoritative policy that prevents duplicate verification starts."""
from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database import get_pool

router = Router()


async def _verification_status(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT language, verification_status, is_verified FROM users WHERE telegram_id=$1",
            telegram_id,
        )


async def block_duplicate_verification_start(callback: CallbackQuery, state: FSMContext):
    """Block a new verification start while the database state is pending/approved."""
    user = await _verification_status(callback.from_user.id)
    if not user:
        await callback.answer("❌ الرجاء البدء أولاً: /start", show_alert=True)
        return

    lang = user["language"] or "ar"
    status = user["verification_status"]
    if status == "pending":
        await state.clear()
        await callback.answer(
            "⏳ <b>طلب التوثيق قيد المراجعة</b>\n\nتم استلام بياناتك وهي الآن لدى الإدارة للمراجعة. لا تحتاج إلى إعادة إرسالها."
            if lang == "ar" else
            "⏳ <b>Verification is under review</b>\n\nYour verification data has already been received and is being reviewed. You do not need to resend it.",
            show_alert=True,
            parse_mode="HTML",
        )
        return

    if user["is_verified"] or status == "approved":
        await state.clear()
        await callback.answer(
            "✅ حسابك موثق بالفعل ولا تحتاج إلى طلب جديد."
            if lang == "ar" else
            "✅ Your account is already verified and does not need a new request.",
            show_alert=True,
        )
        return

    raise SkipHandler


router.callback_query.register(block_duplicate_verification_start, F.data == "start_verification")
