"""Authoritative admin rejection and confirmed-manipulation flows."""
import html
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import (
    admin_menu_keyboard,
    misconduct_final_review_keyboard,
    manipulation_confirmation_keyboard,
    receipt_upload_keyboard,
)
from keyboards.reply import compact_reply_keyboard
from services.formatters import usdt
from services.order_state_service import InvalidOrderTransition, transition_order
from services.user_misconduct_service import (
    MAX_CONFIRMED_INCIDENTS,
    clear_suspension,
    confirm_manipulation,
    customer_notice,
    permanent_ban,
)

logger = logging.getLogger(__name__)
router = Router()
MAX_RECEIPT_ATTEMPTS = 3


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def _sync_customer_status(bot: Bot, order, text: str):
    message_id = order.get("customer_status_message_id")
    if not message_id:
        return
    try:
        await bot.edit_message_text(
            chat_id=order["telegram_id"],
            message_id=int(message_id),
            text=text,
            parse_mode="HTML",
        )
    except Exception:
        logger.warning(
            "Could not update customer status message for order %s",
            order["order_number"],
            exc_info=True,
        )


def _remaining_payment_time(order) -> str:
    deadline = order.get("payment_deadline")
    if not deadline:
        return ""
    seconds = int((deadline - datetime.now()).total_seconds())
    if seconds <= 0:
        return ""
    return f"⏱ الوقت المتبقي: <b>{seconds // 60} دقيقة و{seconds % 60} ثانية</b>"


def _manipulation_available(order) -> bool:
    return int(order.get("receipt_upload_count") or 0) >= MAX_RECEIPT_ATTEMPTS


@router.callback_query(F.data.startswith("admin_reject_receipt_"))
async def reject_receipt(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.replace("admin_reject_receipt_", ""))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id, u.full_name, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )
        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True)
            return
        if order["status"] != "receipt_received":
            await callback.answer("لا يمكن رفض الإيصال من الحالة الحالية", show_alert=True)
            return

        try:
            await transition_order(conn, order_id, "waiting_payment", admin_id=callback.from_user.id)
        except InvalidOrderTransition as exc:
            logger.warning("Receipt rejection transition failed for order %s: %s", order_id, exc)
            await callback.answer("لا يمكن تغيير حالة الطلب من الحالة الحالية", show_alert=True)
            return

    remaining = _remaining_payment_time(order)
    lang = order["language"] or "ar"
    status_text = (
        f"⚠️ <b>تم رفض إيصال الطلب #{html.escape(order['order_number'])}</b>\n\n"
        "📎 تم رفض الإيصال من الإدارة. أرسل إيصالاً جديداً واضحاً لإعادة المراجعة.\n"
        f"{remaining}"
    ) if lang == "ar" else (
        f"⚠️ <b>Receipt rejected for order #{html.escape(order['order_number'])}</b>\n\n"
        "📎 Please upload a clear new receipt for another review.\n"
        f"{remaining}"
    )

    bot = Bot(token=Config.BOT_TOKEN)
    await _sync_customer_status(bot, order, status_text)
    try:
        await bot.send_message(
            order["telegram_id"],
            "⚠️ <b>تم رفض الإيصال</b>\n\n"
            f"عذراً {html.escape(order['full_name'] or 'عميلنا العزيز')}، الإيصال غير مطابق أو غير واضح.\n\n"
            "📌 أرسل إيصالاً جديداً يظهر المبلغ واسم المستفيد والتاريخ.\n\n"
            "📎 اضغط لإعادة رفع الإيصال.\n"
            f"{remaining}\n\n"
            "⚠️ إذا انتهت المهلة سيتم إلغاء الطلب تلقائياً.",
            reply_markup=receipt_upload_keyboard(order_id, lang),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to notify receipt rejection for order %s", order_id)

    await callback.answer("❌ تم رفض الإيصال!")
    if _manipulation_available(order):
        admin_text = (
            f"⚠️ <b>تم رفض الإيصال · الطلب #{html.escape(order['order_number'])}</b>\n\n"
            f"استُنفدت محاولات الإيصال ({MAX_RECEIPT_ATTEMPTS}/{MAX_RECEIPT_ATTEMPTS}).\n"
            "إذا كان الرفض بسبب محاولة تلاعب، يجب على الأدمن تأكيد ذلك صراحة قبل تسجيل مخالفة."
        )
        await callback.message.edit_text(
            admin_text,
            parse_mode="HTML",
            reply_markup=manipulation_confirmation_keyboard(order_id),
        )
    else:
        await callback.message.edit_text(
            f"❌ تم رفض إيصال الطلب #{order['order_number']}",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("admin_reject_"), ~F.data.startswith("admin_reject_receipt_"))
async def reject_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.replace("admin_reject_", ""))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT o.*, u.telegram_id AS user_tg, u.full_name, u.language "
            "FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = $1",
            order_id,
        )
        if not order:
            await callback.answer("الطلب غير موجود", show_alert=True)
            return
        if order["status"] not in ("pending", "waiting_payment", "receipt_received"):
            await callback.answer("لا يمكن رفض الطلب من حالته الحالية", show_alert=True)
            return

        try:
            await transition_order(
                conn,
                order_id,
                "rejected",
                admin_id=callback.from_user.id,
                updates={"receipt_photo_id": None},
            )
        except InvalidOrderTransition as exc:
            logger.warning("Order rejection transition failed for %s: %s", order_id, exc)
            await callback.answer("لا يمكن رفض الطلب من الحالة الحالية", show_alert=True)
            return

    lang = order["language"] or "ar"
    bot = Bot(token=Config.BOT_TOKEN)
    status_text = (
        f"❌ <b>تم رفض الطلب #{html.escape(order['order_number'])}</b>\n\n"
        "لن يتم تنفيذ أي دفع أو تحويل لهذا الطلب. يمكنك إنشاء طلب جديد من القائمة."
        if lang == "ar" else
        f"❌ <b>Order #{html.escape(order['order_number'])} was rejected</b>\n\n"
        "No payment or transfer will be processed for this order. You can create a new order."
    )
    await _sync_customer_status(bot, order, status_text)
    try:
        text = (
            f"❌ <b>تم رفض طلبك</b>\n\n📦 الطلب: #{order['order_number']}\n"
            f"💰 المبلغ: {usdt(order['amount_usdt'])} USDT\n\n"
            "يمكنك إنشاء طلب جديد من القائمة السفلية."
        ) if lang == "ar" else (
            f"❌ <b>Your order was rejected</b>\n\n📦 Order: #{order['order_number']}\n"
            f"💰 Amount: {usdt(order['amount_usdt'])} USDT\n\n"
            "You can create a new order from the bottom menu."
        )
        await bot.send_message(
            order["user_tg"],
            text,
            parse_mode="HTML",
            reply_markup=compact_reply_keyboard(lang),
        )
    except Exception:
        logger.exception("Failed to notify order rejection for %s", order_id)

    await callback.answer("❌ تم رفض الطلب!")
    if _manipulation_available(order):
        admin_text = (
            f"❌ <b>تم رفض الطلب #{html.escape(order['order_number'])}</b>\n\n"
            f"استُنفدت محاولات الإيصال ({MAX_RECEIPT_ATTEMPTS}/{MAX_RECEIPT_ATTEMPTS}).\n"
            "إذا كان الرفض يمثل محاولة تلاعب، يجب على الأدمن تأكيد ذلك صراحة."
        )
        await callback.message.edit_text(
            admin_text,
            parse_mode="HTML",
            reply_markup=manipulation_confirmation_keyboard(order_id),
        )
    else:
        await callback.message.edit_text(
            f"❌ تم رفض الطلب #{order['order_number']}",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("admin_confirm_manipulation_"))
async def confirm_manipulation_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.removeprefix("admin_confirm_manipulation_"))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                SELECT o.*, u.id AS customer_id, u.telegram_id, u.full_name, u.language
                FROM orders o
                JOIN users u ON o.user_id = u.id
                WHERE o.id = $1
                FOR UPDATE OF o, u
                """,
                order_id,
            )
            if not order:
                await callback.answer("الطلب غير موجود", show_alert=True)
                return
            if int(order["receipt_upload_count"] or 0) < MAX_RECEIPT_ATTEMPTS:
                await callback.answer("لم تُستنفد محاولات الإيصال بعد", show_alert=True)
                return
            if order["status"] not in ("rejected", "waiting_payment"):
                await callback.answer("لا يمكن تصنيف الطلب من حالته الحالية", show_alert=True)
                return
            already_classified = await conn.fetchval(
                "SELECT 1 FROM misconduct_incidents WHERE order_id = $1 LIMIT 1",
                order_id,
            )
            if already_classified:
                await callback.answer("تم تصنيف هذا الطلب مسبقاً", show_alert=True)
                return

            try:
                decision = await confirm_manipulation(
                    conn,
                    user_id=order["customer_id"],
                    telegram_id=order["telegram_id"],
                    order_id=order_id,
                    admin_id=callback.from_user.id,
                )
            except ValueError as exc:
                logger.warning("Manipulation classification rejected for order %s: %s", order_id, exc)
                await callback.answer("تعذر تسجيل المخالفة: " + str(exc), show_alert=True)
                return

    lang = order["language"] or "ar"
    bot = Bot(token=Config.BOT_TOKEN)
    try:
        await bot.send_message(
            order["telegram_id"],
            customer_notice(decision, lang),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to notify customer about misconduct decision for order %s", order_id)

    admin_summary = (
        f"⚠️ <b>تم تأكيد محاولة تلاعب</b>\n\n"
        f"📦 الطلب: #{html.escape(order['order_number'])}\n"
        f"👤 العميل: <b>{html.escape(order['full_name'] or 'N/A')}</b>\n"
        f"🆔 <code>{order['telegram_id']}</code>\n"
        f"🔢 المخالفة المؤكدة: <b>{decision.incident_number}/{MAX_CONFIRMED_INCIDENTS}</b>\n"
    )
    if decision.incident_number == 1:
        admin_summary += "🚫 الإجراء: تعليق الخدمة لمدة 4 ساعات."
    elif decision.incident_number == 2:
        admin_summary += "🚫 الإجراء: تعليق الخدمة لمدة 24 ساعة + وضع الحساب للمراجعة."
    else:
        admin_summary += "🛑 الإجراء: تعليق الحساب حتى القرار النهائي. هذه الفرصة الأخيرة."

    if decision.final_warning:
        admin_summary += "\n\nاختر القرار النهائي لهذا الحساب:"
        await callback.message.edit_text(
            admin_summary,
            parse_mode="HTML",
            reply_markup=misconduct_final_review_keyboard(order["telegram_id"]),
        )
    else:
        await callback.message.edit_text(admin_summary, parse_mode="HTML")

    for admin_id in Config.ADMIN_IDS:
        if admin_id == callback.from_user.id:
            continue
        try:
            await bot.send_message(admin_id, admin_summary, parse_mode="HTML")
        except Exception:
            logger.warning("Failed to notify admin %s about misconduct incident", admin_id, exc_info=True)

    await callback.answer(f"⚠️ تم تسجيل المخالفة رقم {decision.incident_number}", show_alert=True)


@router.callback_query(F.data.startswith("admin_dismiss_manipulation_"))
async def dismiss_manipulation_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    try:
        order_id = int(callback.data.removeprefix("admin_dismiss_manipulation_"))
    except ValueError:
        await callback.answer("❌ رقم الطلب غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_logs (user_id, admin_id, action, details, severity)
            SELECT user_id, $2, 'manipulation_not_confirmed', $3, 'info'
            FROM orders WHERE id = $1
            """,
            order_id,
            callback.from_user.id,
            f"Admin dismissed manipulation classification for order {order_id}",
        )
    await callback.message.edit_text(
        f"↩️ <b>تم تسجيل الرفض كمراجعة عادية</b>\n\nالطلب #{order_id} لم يُسجل كمخالفة تلاعب.",
        parse_mode="HTML",
    )
    await callback.answer("تم إلغاء تصنيف التلاعب")


@router.callback_query(F.data.startswith("misconduct_continue_"))
async def misconduct_continue(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    try:
        telegram_id = int(callback.data.removeprefix("misconduct_continue_"))
    except ValueError:
        await callback.answer("❌ معرف غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            incident_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM misconduct_incidents mi
                JOIN users u ON u.id = mi.user_id
                WHERE u.telegram_id = $1
                """,
                telegram_id,
            )
            if int(incident_count or 0) < MAX_CONFIRMED_INCIDENTS:
                await callback.answer("لا يوجد قرار نهائي مستحق لهذا الحساب", show_alert=True)
                return
            await clear_suspension(
                conn,
                telegram_id=telegram_id,
                admin_id=callback.from_user.id,
                decision="allow_continue",
            )

    bot = Bot(token=Config.BOT_TOKEN)
    try:
        await bot.send_message(
            telegram_id,
            "✅ <b>تم السماح باستمرار حسابك</b>\n\nبعد المراجعة الإدارية، تقرر استمرار الخدمة. هذه هي الفرصة الأخيرة، وأي محاولة تلاعب مؤكدة لاحقاً قد تؤدي إلى الحظر النهائي.",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to notify customer after misconduct continuation decision")
    await callback.message.edit_text(
        f"✅ <b>تم السماح باستمرار الحساب</b>\n🆔 <code>{telegram_id}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer("تم السماح بالاستمرار")


@router.callback_query(F.data.startswith("misconduct_ban_"))
async def misconduct_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    try:
        telegram_id = int(callback.data.removeprefix("misconduct_ban_"))
    except ValueError:
        await callback.answer("❌ معرف غير صالح", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                await permanent_ban(
                    conn,
                    telegram_id=telegram_id,
                    admin_id=callback.from_user.id,
                    reason="Permanent ban after third confirmed payment-receipt manipulation incident",
                )
            except ValueError as exc:
                await callback.answer("تعذر تنفيذ الحظر: " + str(exc), show_alert=True)
                return

    bot = Bot(token=Config.BOT_TOKEN)
    try:
        await bot.send_message(
            telegram_id,
            "🚫 <b>تم حظر الحساب نهائياً</b>\n\nبعد المراجعة الإدارية، تقرر إيقاف الخدمة نهائياً بسبب تكرار محاولات التلاعب المؤكدة.",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to notify customer about permanent ban")
    await callback.message.edit_text(
        f"🚫 <b>تم حظر الحساب نهائياً</b>\n🆔 <code>{telegram_id}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer("تم الحظر النهائي")


@router.callback_query(F.data.startswith("admin_noop"))
async def admin_noop(callback: CallbackQuery):
    await callback.answer("⏳ الطلب في انتظار الدفع من العميل...", show_alert=True)
