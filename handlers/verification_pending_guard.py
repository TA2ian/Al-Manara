"""Guards against duplicate customer verification submissions.

The legacy verification flow can leave the FSM in the QR state after a
successful submission. This router runs before the verification router and
makes the database verification status authoritative: a user with a pending
review cannot start or submit another verification request.
"""
from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import get_pool
from states import VerificationStates

router = Router()


async def _verification_status(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, language, verification_status, is_verified "
            "FROM users WHERE telegram_id = $1",
            telegram_id,
        )
    return row


@router.callback_query(F.data == "start_verification")
async def block_duplicate_verification_start(callback: CallbackQuery, state: FSMContext):
    """Prevent restarting verification while a review is already pending."""
    user = await _verification_status(callback.from_user.id)
    if not user:
        await callback.answer("❌ الرجاء البدء أولاً: /start", show_alert=True)
        return

    lang = user["language"] or "ar"
    status = user["verification_status"]
    if status == "pending":
        await state.clear()
        await callback.answer(
            "⏳ لديك طلب توثيق قيد المراجعة بالفعل. لا يمكنك إرسال طلب توثيق جديد حتى تنتهي الإدارة من مراجعة الطلب الحالي."
            if lang == "ar" else
            "⏳ You already have a verification request under review. You cannot submit another request until the current review is completed.",
            show_alert=True,
        )
        return

    if user["is_verified"] or status == "approved":
        await state.clear()
        await callback.answer(
            "✅ حسابك موثق بالفعل. لا تحتاج إلى إرسال طلب توثيق جديد."
            if lang == "ar" else
            "✅ Your account is already verified. You do not need to submit another verification request.",
            show_alert=True,
        )
        return

    # Let the authoritative verification router handle the normal flow.
    raise SkipHandler


@router.message(VerificationStates.waiting_shamcash_qr, F.photo)
async def guard_verification_qr_submission(message: Message, state: FSMContext):
    """Stop stale FSM sessions from creating a second pending request."""
    user = await _verification_status(message.from_user.id)
    if not user:
        await state.clear()
        return

    lang = user["language"] or "ar"
    status = user["verification_status"]
    if status == "pending":
        await state.clear()
        await message.answer(
            "⏳ تم إرسال طلب التوثيق بالفعل وهو قيد المراجعة. لا يمكن إرسال طلب توثيق ثانٍ قبل انتهاء المراجعة."
            if lang == "ar" else
            "⏳ Your verification request has already been submitted and is under review. A second request cannot be submitted before the review is completed."
        )
        return

    if user["is_verified"] or status == "approved":
        await state.clear()
        await message.answer(
            "✅ حسابك موثق بالفعل ولا يحتاج إلى طلب توثيق جديد."
            if lang == "ar" else
            "✅ Your account is already verified and does not need a new verification request."
        )
        return

    # For rejected/not_verified users, preserve the existing verification
    # submission implementation by delegating to it after recording the QR.
    await state.update_data(shamcash_qr_photo_id=message.photo[-1].file_id)
    from handlers.verification import submit_verification
    await submit_verification(message, state)
