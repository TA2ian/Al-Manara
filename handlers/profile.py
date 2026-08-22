"""Profile handlers."""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from keyboards.inline import main_menu_inline, start_verification_keyboard
from services.locale_service import locale_service
from database import get_pool

router = Router()


@router.callback_query(F.data == "menu_profile")
async def show_profile(callback: CallbackQuery):
    """Show the user's real verification state and the next required action."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            callback.from_user.id
        )

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    lang = user['language'] or 'ar'
    is_verified = bool(user['is_verified'])
    verification_status = (user['verification_status'] or '').strip().lower()

    # A user is not "pending review" merely because the database has a legacy
    # default value. Pending is truthful only after a verification submission
    # containing the required review data.
    has_submitted_verification = bool(
        user['phone_verified']
        and user['phone_number']
        and user['full_name']
        and user['shamcash_account']
        and user['shamcash_qr_photo_id']
        and verification_status == 'pending'
    )

    if is_verified or verification_status == 'approved':
        status = "✅ موثق" if lang == 'ar' else "✅ Verified"
        verification_markup = None
    elif verification_status == 'rejected':
        status = "❌ غير موثق — تم رفض التوثيق" if lang == 'ar' else "❌ Unverified — verification rejected"
        verification_markup = start_verification_keyboard(lang)
    elif has_submitted_verification:
        status = "⏳ قيد مراجعة التوثيق" if lang == 'ar' else "⏳ Verification under review"
        verification_markup = None
    else:
        status = "⚠️ غير موثق بعد" if lang == 'ar' else "⚠️ Not verified yet"
        verification_markup = start_verification_keyboard(lang)

    text = locale_service.get(
        'profile_info',
        lang,
        telegram_id=user['telegram_id'],
        full_name=user['full_name'] or 'N/A',
        status=status,
        language=locale_service.get_language_name(lang),
        created_at=user['created_at'].strftime('%Y-%m-%d') if user['created_at'] else 'N/A'
    )

    await callback.message.edit_text(text, parse_mode='HTML')
    if verification_markup:
        await callback.message.answer(
            "🔒 <b>حسابك غير موثق بعد.</b>\n\nاضغط على الزر أدناه لبدء عملية التحقق وإرسال بياناتك للمراجعة من الإدارة."
            if lang == 'ar' else
            "🔒 <b>Your account is not verified yet.</b>\n\nUse the button below to start verification and submit your details for admin review.",
            parse_mode='HTML',
            reply_markup=verification_markup,
        )
    await callback.message.answer(
        locale_service.get('main_menu', lang),
        reply_markup=main_menu_inline(lang)
    )
    await callback.answer()
