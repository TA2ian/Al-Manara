"""Policy router that blocks duplicate customer verification submissions.

The verification status stored in the database is authoritative. A user with a
pending review cannot restart verification or submit another QR. Users whose
request is not pending continue through the authoritative verification flow.
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
            "⏳ <b>طلب التوثيق قيد المراجعة</b>\n\n"
            "تم استلام بياناتك بالفعل وهي الآن لدى الإدارة للمراجعة.\n"
            "لا تحتاج إلى إعادة إرسال أي بيانات أو إنشاء طلب توثيق جديد.\n\n"
            "🔒 لحماية حسابك ومنع تكرار الطلبات، لن يسمح النظام بإرسال طلب توثيق آخر حتى تنتهي مراجعة الطلب الحالي.\n\n"
            "📩 سيتم إبلاغك عند اعتماد الحساب أو رفض الطلب."
            if lang == "ar" else
            "⏳ <b>Verification is under review</b>\n\n"
            "Your verification details have already been received and are now being reviewed by the admin team.\n"
            "You do not need to resend any information or create another verification request.\n\n"
            "🔒 To protect your account and prevent duplicate requests, another verification request cannot be submitted until the current review is completed.\n\n"
            "📩 You will be notified when your account is approved or your request is rejected.",
            show_alert=True,
            parse_mode="HTML",
        )
        return

    if user["is_verified"] or status == "approved":
        await state.clear()
        await callback.answer(
            "✅ حسابك موثق بالفعل. لا تحتاج إلى إرسال طلب توثيق جديد.\n\n"
            "يمكنك الآن استخدام الخدمات المتاحة لحسابك."
            if lang == "ar" else
            "✅ Your account is already verified. You do not need to submit a new verification request.\n\n"
            "You can now use the services available to your account.",
            show_alert=True,
            parse_mode="HTML",
        )
        return

    raise SkipHandler


router.callback_query.register(block_duplicate_verification_start, F.data == "start_verification")


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
            "⏳ <b>تم استلام طلب التوثيق</b>\n\n"
            "طلبك الحالي قيد المراجعة لدى الإدارة، لذلك لا حاجة لإرسال صورة QR أو أي بيانات مرة أخرى.\n\n"
            "🔒 تم منع إنشاء طلب توثيق ثانٍ حتى تنتهي مراجعة الطلب الحالي.\n\n"
            "📩 سنبلغك بالنتيجة عند انتهاء المراجعة."
            if lang == "ar" else
            "⏳ <b>Verification request already received</b>\n\n"
            "Your current request is under admin review, so there is no need to send the QR image or any information again.\n\n"
            "🔒 A second verification request is blocked until the current review is completed.\n\n"
            "📩 We will notify you when the review is complete.",
            parse_mode="HTML",
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

    await state.update_data(shamcash_qr_photo_id=message.photo[-1].file_id)
    from handlers.verification import submit_verification
    await submit_verification(message, state)
