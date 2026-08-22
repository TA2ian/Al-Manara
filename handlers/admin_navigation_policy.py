"""Authoritative admin navigation, search, analytics, and input-state policy."""
import html
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard
from services.settings_service import SettingsService
from states import AdminStates

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء والعودة للوحة التحكم", callback_data="admin_cancel_input")]
    ])


async def _show_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_cancel_input")
async def cancel_admin_input(callback: CallbackQuery, state: FSMContext):
    """Cancel any unfinished admin text-entry flow."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_admin_menu(callback, state)
    await callback.answer("تم الإلغاء")


@router.callback_query(F.data == "admin_analytics")
async def financial_analytics(callback: CallbackQuery, state: FSMContext):
    """Show financial/business analytics only; customer data belongs elsewhere."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    await state.clear()
    pool = await get_pool()
    async with pool.acquire() as conn:
        completed = await conn.fetchrow(
            """SELECT COUNT(*) AS count,
                      COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders WHERE status = 'completed'"""
        )
        active = await conn.fetchrow(
            """SELECT COUNT(*) AS count,
                      COALESCE(SUM(amount_usdt), 0) AS usdt
               FROM orders
               WHERE status IN ('pending','waiting_payment','receipt_received','payment_confirmed')"""
        )
        today = await conn.fetchrow(
            """SELECT COUNT(*) AS count,
                      COALESCE(SUM(amount_usdt), 0) AS usdt,
                      COALESCE(SUM(fee_amount), 0) AS fees
               FROM orders
               WHERE created_at >= CURRENT_DATE AND status = 'completed'"""
        )
        currency_rows = await conn.fetch(
            """SELECT payment_currency,
                      COUNT(*) AS count,
                      COALESCE(SUM(total_amount), 0) AS total
               FROM orders
               WHERE status = 'completed'
               GROUP BY payment_currency
               ORDER BY payment_currency"""
        )

    currency_lines = []
    for row in currency_rows:
        currency_lines.append(
            f"• {row['payment_currency']}: {row['count']} طلب — {row['total']:,.2f}"
        )
    currency_text = "\n".join(currency_lines) if currency_lines else "• لا توجد بيانات مكتملة بعد"

    text = (
        "📈 <b>التحليل المالي</b>\n\n"
        "━━━ الأداء المالي ━━━\n"
        f"💰 USDT المسلم: <b>{completed['usdt']:,.2f}</b>\n"
        f"💵 رسوم محققة: <b>{completed['fees']:,.2f}</b>\n"
        f"📦 طلبات مكتملة: <b>{completed['count']}</b>\n\n"
        "━━━ اليوم ━━━\n"
        f"📦 مكتمل: <b>{today['count']}</b>\n"
        f"💰 USDT: <b>{today['usdt']:,.2f}</b>\n"
        f"💵 رسوم: <b>{today['fees']:,.2f}"
        f"\n\n━━━ قيد التنفيذ ━━━\n"
        f"⏳ الطلبات النشطة: <b>{active['count']}</b>\n"
        f"💰 قيمتها: <b>{active['usdt']:,.2f} USDT</b>\n\n"
        "━━━ حسب عملة الدفع ━━━\n"
        f"{currency_text}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_search_order")
async def search_order_start(callback: CallbackQuery, state: FSMContext):
    """Start order search with an explicit cancellation path."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🔍 <b>بحث عن طلب</b>\n\n"
        "أرسل رقم الطلب الذي يبدأ بـ <code>ORD_</code>.\n"
        "مثال: <code>ORD_20260730_ABC123</code>",
        reply_markup=_cancel_keyboard(),
        parse_mode="HTML",
    )
    await state.update_data(admin_search_type="order")
    await state.set_state(AdminStates.waiting_search)
    await callback.answer()


@router.message(AdminStates.waiting_search)
async def search_handler(message: Message, state: FSMContext):
    """Handle admin search and always terminate the search state."""
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return

    data = await state.get_data()
    search_type = data.get("admin_search_type", "user")
    query = (message.text or "").strip()
    pool = await get_pool()

    if search_type == "order":
        if not query.upper().startswith("ORD_") or len(query) < 8:
            await state.clear()
            await message.answer(
                "❌ صيغة رقم الطلب غير صحيحة. يجب أن يبدأ الرقم بـ <code>ORD_</code>.\n\n"
                "تم إلغاء البحث. يمكنك بدء بحث جديد من لوحة التحكم.",
                reply_markup=admin_menu_keyboard(),
                parse_mode="HTML",
            )
            return

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT o.*, u.full_name, u.telegram_id
                   FROM orders o JOIN users u ON o.user_id = u.id
                   WHERE o.order_number ILIKE $1""",
                query,
            )

        await state.clear()
        if not row:
            await message.answer(
                "❌ لم يتم العثور على طلب بهذا الرقم.",
                reply_markup=admin_menu_keyboard(),
            )
            return

        wallet = html.escape(row["wallet_address"] or "")
        text = (
            f"📦 <b>الطلب #{html.escape(row['order_number'])}</b>\n\n"
            f"👤 العميل: {html.escape(row['full_name'] or 'N/A')}\n"
            f"🆔 <code>{row['telegram_id']}</code>\n"
            f"💰 {row['amount_usdt']} USDT → {row['network']}\n"
            f"📍 المحفظة: <code>{wallet}</code>\n"
            f"📊 الحالة: {row['status']}\n"
            f"💱 السعر: 1 USDT = {row['exchange_rate']:,.2f} {row['payment_currency']}\n"
            f"💵 الإجمالي: {row['total_amount']:,.2f} {row['payment_currency']}\n"
            f"📅 الإنشاء: {row['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")]
            ]),
        )
        return

    clean = query.replace("@", "")
    async with pool.acquire() as conn:
        if query.isdigit():
            rows = await conn.fetch("SELECT * FROM users WHERE telegram_id = $1", int(query))
        else:
            rows = await conn.fetch("SELECT * FROM users WHERE username ILIKE $1", f"%{clean}%")

    await state.clear()
    if not rows:
        await message.answer("❌ لم يتم العثور على مستخدم.", reply_markup=admin_menu_keyboard())
        return

    for user in rows:
        text = (
            f"👤 <b>معلومات العميل</b>\n\n"
            f"🆔 المعرف: <code>{user['telegram_id']}</code>\n"
            f"📛 الاسم: {html.escape(user['full_name'] or 'N/A')}\n"
            f"📱 اليوزر: @{html.escape(user['username'] or 'N/A')}\n"
            f"🔰 التوثيق: {'✅' if user['is_verified'] else '❌'} ({user['verification_status']})\n"
            f"🏦 شام كاش: {html.escape(user['shamcash_account'] or 'N/A')}\n"
            f"💬 اللغة: {user['language']}\n"
            f"🚫 محظور: {'✅' if user['is_blocked'] else '❌'}\n"
            f"📅 التسجيل: {user['created_at'].strftime('%Y-%m-%d')}"
        )
        tid = user["telegram_id"]
        action = "admin_unban_" if user["is_blocked"] else "admin_ban_"
        action_text = "✅ فك الحظر" if user["is_blocked"] else "🚫 حظر"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=action_text, callback_data=f"{action}{tid}"),
             InlineKeyboardButton(text="🗑️ حذف", callback_data=f"admin_del_user_{tid}")],
            [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
        ])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "setting_fees")
async def fee_settings_start(callback: CallbackQuery, state: FSMContext):
    """Start persistent fee configuration without misleading temporary-change text."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    current = await SettingsService.get("service_fee_percent", str(Config.SERVICE_FEE_PERCENT))
    await callback.message.edit_text(
        "⚙️ <b>الرسوم الحالية</b>\n\n"
        f"📊 نسبة الرسوم: <b>{current}%</b>\n\n"
        "أرسل نسبة الرسوم الجديدة من 0 إلى 100.",
        reply_markup=_cancel_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_fee_percent)
    await callback.answer()


@router.message(AdminStates.waiting_fee_percent)
async def fee_settings_save(message: Message, state: FSMContext):
    """Persist fee percentage so it survives restart."""
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    try:
        pct = float((message.text or "").strip())
        if pct < 0 or pct > 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ نسبة غير صالحة. أرسل رقماً بين 0 و100.", reply_markup=_cancel_keyboard())
        return

    Config.SERVICE_FEE_PERCENT = pct
    await SettingsService.set("service_fee_percent", str(pct))
    await state.clear()
    await message.answer(
        f"✅ تم حفظ نسبة الرسوم: <b>{pct:g}%</b>\n\n"
        "سيتم تطبيقها على عروض الأسعار الجديدة.",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "setting_rate")
async def rate_settings_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rate = await conn.fetchval("SELECT rate FROM exchange_rates ORDER BY updated_at DESC LIMIT 1")
    await callback.message.edit_text(
        f"💱 <b>سعر الصرف الحالي:</b> 1 USDT = {rate:,.2f} NEW.SYP\n\nأرسل السعر الجديد:",
        reply_markup=_cancel_keyboard(),
        parse_mode="HTML",
    )
    await state.update_data(admin_rate_prompt_message_id=callback.message.message_id)
    await state.set_state(AdminStates.waiting_rate)
    await callback.answer()


@router.message(AdminStates.waiting_rate)
async def rate_settings_save(message: Message, state: FSMContext):
    """Save the exchange rate and immediately terminate the input flow."""
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return

    try:
        new_rate = float((message.text or "").strip().replace(",", ""))
        if new_rate <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ سعر غير صالح. أرسل رقماً موجباً (مثال: 15000):",
            reply_markup=_cancel_keyboard(),
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO exchange_rates (rate, updated_by) VALUES ($1, $2)",
            new_rate,
            message.from_user.id,
        )

    data = await state.get_data()
    prompt_message_id = data.get("admin_rate_prompt_message_id")

    # Clear the FSM before any UI transition so no later message is consumed by
    # the old rate-entry state.
    await state.clear()

    # Replace the original input prompt instead of leaving a stale/blurred
    # message open in the chat. This follows the system's edit-in-place pattern.
    if prompt_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_message_id,
                text=(
                    f"✅ <b>تم تحديث سعر الصرف</b>\n\n"
                    f"1 USDT = <b>{new_rate:,.0f} NEW.SYP</b>"
                ),
                reply_markup=admin_menu_keyboard(),
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Could not replace exchange-rate prompt: %s", exc)
            await message.answer(
                f"✅ تم تحديث سعر الصرف: 1 USDT = {new_rate:,.0f} NEW.SYP",
                reply_markup=admin_menu_keyboard(),
                parse_mode="HTML",
            )
    else:
        await message.answer(
            f"✅ تم تحديث سعر الصرف: 1 USDT = {new_rate:,.0f} NEW.SYP",
            reply_markup=admin_menu_keyboard(),
            parse_mode="HTML",
        )

    # Remove the raw rate input from the admin chat when possible; the final
    # result remains visible in the edited prompt above.
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "setting_timeout")
async def timeout_settings_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"⏱ <b>مهلة الدفع الحالية:</b> {Config.PAYMENT_TIMEOUT} دقيقة\n\nأرسل المهلة الجديدة بالدقائق:",
        reply_markup=_cancel_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_timeout)
    await callback.answer()


@router.callback_query(F.data == "setting_limits")
async def limits_settings_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        f"📊 <b>الحدود الحالية</b>\n\n🔽 الحد الأدنى: {Config.MIN_ORDER} USDT\n🔼 الحد الأقصى: {Config.MAX_ORDER} USDT\n\nأرسل الحد الأدنى الجديد:",
        reply_markup=_cancel_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_min_order)
    await callback.answer()
