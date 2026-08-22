"""Authoritative admin verification policy.

Telegram username is mutable and is never required for identity or approval.
The stable identity is telegram_id; phone ownership, ShamCash account data,
and the submitted ShamCash QR are the review requirements.
"""
import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import main_menu_inline

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


@router.callback_query(F.data.startswith("verify_approve_"))
async def approve_verification(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    telegram_id = int(callback.data.replace("verify_approve_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """SELECT id, language, phone_number, phone_verified, full_name,
                      shamcash_account, shamcash_qr_photo_id, verification_status
               FROM users WHERE telegram_id=$1""",
            telegram_id,
        )
        if not user:
            await callback.answer("المستخدم غير موجود", show_alert=True)
            return
        if not user["phone_verified"] or not user["phone_number"]:
            await callback.answer("❌ رقم الهاتف غير موثق", show_alert=True)
            return
        if not user["shamcash_account"] or not user["shamcash_qr_photo_id"]:
            await callback.answer("❌ بيانات ShamCash أو QR ناقصة", show_alert=True)
            return
        if user["verification_status"] != "pending":
            await callback.answer("⚠️ طلب التوثيق ليس في حالة انتظار", show_alert=True)
            return

        await conn.execute(
            "UPDATE users SET is_verified=TRUE, verification_status='approved' WHERE telegram_id=$1",
            telegram_id,
        )
        await conn.execute(
            """INSERT INTO audit_logs (user_id, admin_id, action, details, severity)
               VALUES ($1,$2,'verification_approved',$3,'info')""",
            user["id"], callback.from_user.id,
            "manual review: phone + ShamCash account + ShamCash QR present; Telegram username not used as identity",
        )

    bot = Bot(token=Config.BOT_TOKEN)
    lang = user["language"] or "ar"
    try:
        await bot.send_message(
            telegram_id,
            "🎉 <b>تم توثيق حسابك!</b>\n\nيمكنك الآن إنشاء طلبات شراء USDT."
            if lang == "ar" else
            "🎉 <b>Your account has been verified!</b>\n\nYou can now create USDT purchase orders.",
            parse_mode="HTML",
            reply_markup=main_menu_inline(lang),
        )
    except Exception as exc:
        logger.error("Failed to notify verified user %s: %s", telegram_id, exc)

    await callback.message.edit_text(
        "✅ <b>تم توثيق المستخدم بنجاح.</b>\n"
        "لم يتم استخدام اسم المستخدم في Telegram كمعرّف أو شرط للتوثيق."
        if callback.from_user.id in Config.ADMIN_IDS else
        "✅ Verification approved.",
        parse_mode="HTML",
    )
    await callback.answer("✅ تم التوثيق!")


@router.callback_query(F.data.startswith("verify_reject_"))
async def reject_verification(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    telegram_id = int(callback.data.replace("verify_reject_", ""))
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language, verification_status FROM users WHERE telegram_id=$1",
            telegram_id,
        )
        if not user:
            await callback.answer("المستخدم غير موجود", show_alert=True)
            return
        await conn.execute(
            "UPDATE users SET is_verified=FALSE, verification_status='rejected' WHERE telegram_id=$1",
            telegram_id,
        )
        await conn.execute(
            """INSERT INTO audit_logs (user_id, admin_id, action, details, severity)
               VALUES ($1,$2,'verification_rejected','manual ShamCash verification review rejected','warning')""",
            user["id"], callback.from_user.id,
        )

    bot = Bot(token=Config.BOT_TOKEN)
    lang = user["language"] or "ar"
    try:
        await bot.send_message(
            telegram_id,
            "❌ <b>لم يتم توثيق حسابك.</b>\n\nيرجى مراجعة بيانات ShamCash والتواصل مع الدعم."
            if lang == "ar" else
            "❌ <b>Your account was not verified.</b>\n\nPlease review your ShamCash details and contact support.",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error("Failed to notify rejected user %s: %s", telegram_id, exc)

    await callback.message.edit_text(
        "❌ تم رفض توثيق المستخدم." if callback.from_user.id in Config.ADMIN_IDS else "❌ Verification rejected.",
        parse_mode="HTML",
    )
    await callback.answer("❌ تم الرفض!")
