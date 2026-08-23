"""Admin management for persistent ShamCash payment accounts and QR codes."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from database import get_pool
from keyboards.inline import payment_methods_keyboard, payment_method_actions, admin_menu_keyboard
from services.settings_service import SettingsService

router = Router()


class PaymentMethodStates(StatesGroup):
    waiting_account = State()
    waiting_qr = State()


# NEW.SYP is the only Syrian payment currency. Legacy SYP is display-only.
CURRENCY_META = {
    "USD": ("USD", "الدولار الأمريكي"),
    "NEW.SYP": ("NEW.SYP", "الليرة السورية الجديدة"),
}


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def enhanced_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin menu with financial-only analytics wording and payment shortcut."""
    rows = []
    for row in admin_menu_keyboard().inline_keyboard:
        new_row = []
        for button in row:
            if button.callback_data == "admin_analytics":
                new_row.append(InlineKeyboardButton(text="📈 التحليل المالي", callback_data="admin_analytics"))
            else:
                new_row.append(button)
        rows.append(new_row)
    rows.insert(3, [InlineKeyboardButton(text="💳 وسائل الدفع", callback_data="admin_payment_methods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def ensure_default_methods(conn):
    """Ensure exactly one canonical ShamCash method exists per currency.

    Older builds used the code ``shamcash_syp`` while the canonical NEW.SYP
    method is ``shamcash_new_syp``. Merge the legacy record into the canonical
    record before rendering the list so old deployments cannot show duplicates.
    """
    for currency, label in CURRENCY_META.values():
        account = Config.get_shamcash_usd() if currency == "USD" else Config.get_shamcash_syp()
        code = "shamcash_usd" if currency == "USD" else "shamcash_new_syp"
        await conn.execute(
            """INSERT INTO payment_methods
               (code, provider, currency, display_name, account_identifier, enabled)
               VALUES ($1, 'ShamCash', $2, $3, $4, TRUE)
               ON CONFLICT (code) DO UPDATE
               SET currency = EXCLUDED.currency,
                   display_name = EXCLUDED.display_name,
                   updated_at = NOW()""",
            code,
            currency,
            f"ShamCash {label}",
            account,
        )

    # One-time cleanup of the old SYP code. Preserve its account/QR first if
    # the canonical record is still empty.
    legacy = await conn.fetchrow(
        "SELECT account_identifier, qr_photo_id, enabled FROM payment_methods WHERE code = 'shamcash_syp' AND provider = 'ShamCash'"
    )
    canonical = await conn.fetchrow(
        "SELECT account_identifier, qr_photo_id FROM payment_methods WHERE code = 'shamcash_new_syp' AND provider = 'ShamCash'"
    )
    if legacy:
        if canonical:
            if (not canonical["account_identifier"]) and legacy["account_identifier"]:
                await conn.execute(
                    "UPDATE payment_methods SET account_identifier = $1 WHERE code = 'shamcash_new_syp'",
                    legacy["account_identifier"],
                )
            if (not canonical["qr_photo_id"]) and legacy["qr_photo_id"]:
                await conn.execute(
                    "UPDATE payment_methods SET qr_photo_id = $1 WHERE code = 'shamcash_new_syp'",
                    legacy["qr_photo_id"],
                )
        await conn.execute(
            "DELETE FROM payment_methods WHERE code = 'shamcash_syp' AND provider = 'ShamCash'"
        )


@router.message(F.text == "/payment_methods")
async def payment_methods_command(message: Message):
    """Direct admin entry point for payment methods during setup."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        return
    await _show_payment_methods(message)


@router.callback_query(F.data == "admin_menu")
async def enhanced_admin_menu(callback: CallbackQuery, state: FSMContext):
    """Return to the admin dashboard and clear any unfinished input state."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "👨‍💼 <b>لوحة الإدارة</b>\n\nاختر العملية المطلوبة:",
        reply_markup=enhanced_admin_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_payment_methods")
async def payment_methods_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await _show_payment_methods(callback.message, edit=True)
    await callback.answer()


async def _show_payment_methods(target, edit: bool = False):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await ensure_default_methods(conn)
        methods = await conn.fetch(
            "SELECT code, currency, display_name, account_identifier, qr_photo_id, enabled "
            "FROM payment_methods WHERE provider = 'ShamCash' "
            "AND code IN ('shamcash_usd', 'shamcash_new_syp') "
            "ORDER BY CASE currency WHEN 'USD' THEN 1 ELSE 2 END"
        )

    text = "💳 <b>وسائل الدفع — ShamCash</b>\n\n"
    for method in methods:
        status = "🟢 فعال" if method["enabled"] else "🔴 معطل"
        qr = "محفوظ" if method["qr_photo_id"] else "غير محفوظ"
        account = method["account_identifier"] or "غير مضبوط"
        label = "الدولار الأمريكي" if method["currency"] == "USD" else "الليرة السورية الجديدة"
        text += (
            f"<b>{method['currency']}</b> — {label} — {status}\n"
            f"الحساب: <code>{account}</code>\n"
            f"QR: {qr}\n\n"
        )
    text += "اختر وسيلة الدفع لإدارة الحساب ورمز QR المحفوظ."

    if edit:
        await target.edit_text(text, reply_markup=payment_methods_keyboard(methods), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=payment_methods_keyboard(methods), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_pm_view_"))
async def payment_method_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_view_")
    pool = await get_pool()
    async with pool.acquire() as conn:
        method = await conn.fetchrow(
            "SELECT * FROM payment_methods WHERE code = $1 AND provider = 'ShamCash'",
            code,
        )
    if not method:
        await callback.answer("وسيلة الدفع غير موجودة", show_alert=True)
        return

    status = "🟢 فعال" if method["enabled"] else "🔴 معطل"
    qr = "محفوظ" if method["qr_photo_id"] else "غير محفوظ"
    label = "الدولار الأمريكي" if method["currency"] == "USD" else "الليرة السورية الجديدة"
    text = (
        f"💳 <b>ShamCash {method['currency']} — {label}</b>\n\n"
        f"الحالة: {status}\n"
        f"الحساب: <code>{method['account_identifier'] or 'غير مضبوط'}</code>\n"
        f"QR: {qr}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=payment_method_actions(code, method["enabled"]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_pm_account_"))
async def payment_method_account_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_account_")
    await state.update_data(payment_method_code=code)
    await state.set_state(PaymentMethodStates.waiting_account)
    await callback.message.edit_text(
        "💳 <b>تعديل حساب ShamCash</b>\n\nأرسل رقم/عنوان الحساب لهذه العملة:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_payment_methods")]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(PaymentMethodStates.waiting_account)
async def payment_method_account_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    value = (message.text or "").strip()
    data = await state.get_data()
    code = data.get("payment_method_code")
    if not value or len(value) > 200 or not code:
        await message.answer("❌ قيمة غير صالحة. أرسل الحساب مرة أخرى.")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE payment_methods SET account_identifier = $1, updated_at = NOW() "
            "WHERE code = $2 AND provider = 'ShamCash' RETURNING currency",
            value, code,
        )
        if not row:
            await message.answer("❌ وسيلة الدفع غير موجودة.")
            await state.clear()
            return
        await conn.execute(
            """INSERT INTO audit_logs (admin_id, action, details, new_value, severity)
               VALUES ($1, 'payment_method_account_update', $2, $3, 'info')""",
            message.from_user.id, f"payment_method={code}", value,
        )

    if row["currency"] == "USD":
        Config.set_shamcash_usd(value)
        await SettingsService.set("shamcash_usd", value)
    elif row["currency"] == "NEW.SYP":
        Config.set_shamcash_syp(value)
        await SettingsService.set("shamcash_syp", value)

    await message.answer(f"✅ تم حفظ حساب ShamCash لـ {row['currency']}.")
    await state.clear()


@router.callback_query(F.data.startswith("admin_pm_qr_"))
async def payment_method_qr_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_qr_")
    await state.update_data(payment_method_code=code)
    await state.set_state(PaymentMethodStates.waiting_qr)
    await callback.message.edit_text(
        "🖼️ <b>حفظ QR</b>\n\nأرسل صورة QR الخاصة بحساب ShamCash الآن.\nسيتم حفظها ولن تحتاج لإعادة رفعها مع كل طلب.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_payment_methods")]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(PaymentMethodStates.waiting_qr, F.photo)
async def payment_method_qr_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    data = await state.get_data()
    code = data.get("payment_method_code")
    if not code:
        await state.clear()
        await message.answer("❌ انتهت جلسة الإعداد. أعد المحاولة من لوحة الإدارة.")
        return

    file_id = message.photo[-1].file_id
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE payment_methods SET qr_photo_id = $1, updated_at = NOW() "
            "WHERE code = $2 AND provider = 'ShamCash' RETURNING currency",
            file_id, code,
        )
        if not row:
            await message.answer("❌ وسيلة الدفع غير موجودة.")
            await state.clear()
            return
        await conn.execute(
            """INSERT INTO audit_logs (admin_id, action, details, new_value, severity)
               VALUES ($1, 'payment_method_qr_update', $2, $3, 'info')""",
            message.from_user.id, f"payment_method={code}", file_id,
        )

    await message.answer(f"✅ تم حفظ QR الخاص بـ ShamCash {row['currency']}. لن يُطلب رفعه مع كل طلب.")
    await state.clear()


@router.message(PaymentMethodStates.waiting_qr)
async def payment_method_qr_invalid(message: Message):
    if is_admin(message.from_user.id):
        await message.answer("❌ أرسل صورة QR كصورة، وليس كنص أو ملف آخر.")


@router.callback_query(F.data.startswith("admin_pm_toggle_"))
async def payment_method_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_toggle_")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE payment_methods SET enabled = NOT enabled, updated_at = NOW() "
            "WHERE code = $1 AND provider = 'ShamCash' RETURNING currency, enabled",
            code,
        )
        if row:
            await conn.execute(
                """INSERT INTO audit_logs (admin_id, action, details, new_value, severity)
                   VALUES ($1, 'payment_method_toggle', $2, $3, 'info')""",
                callback.from_user.id, f"payment_method={code}", str(row['enabled']),
            )
    if not row:
        await callback.answer("وسيلة الدفع غير موجودة", show_alert=True)
        return
    # payment_method_view renders the updated state and answers the callback;
    # do not acknowledge the same callback twice.
    await payment_method_view(callback)
