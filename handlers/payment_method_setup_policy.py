"""Canonical admin wizard for persistent ShamCash payment methods."""
import html
import io
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from PIL import Image

from config import Config
from database import get_pool
from services.media_security import validate_image_payload

router = Router()
logger = logging.getLogger(__name__)


class PaymentMethodStates(StatesGroup):
    waiting_recipient_name = State()
    waiting_receiving_address = State()
    waiting_qr = State()
    waiting_confirmation = State()


CURRENCY_META = {"USD": "الدولار الأمريكي", "NEW.SYP": "الليرة السورية الجديدة"}
CANONICAL_CODES = {"shamcash_usd", "shamcash_new_syp"}
CANONICAL_CODE_PATTERN = r"(?:shamcash_usd|shamcash_new_syp)"


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_payment_methods")]])


def _methods_keyboard(methods) -> InlineKeyboardMarkup:
    rows = []
    for method in methods:
        status = "🟢" if method["enabled"] else "🔴"
        rows.append([InlineKeyboardButton(text=f"{status} {method['currency']}", callback_data=f"admin_pm_view_{method['code']}")])
    rows.append([InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _view_keyboard(code: str, enabled: bool) -> InlineKeyboardMarkup:
    if enabled:
        action_text = "⏸ تعطيل"
        action_callback = f"admin_pm_disable_{code}"
    else:
        action_text = "▶️ تفعيل"
        action_callback = f"admin_pm_enable_{code}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ إعداد/تعديل بيانات الدفع", callback_data=f"admin_pm_setup_{code}")],
        [InlineKeyboardButton(text=action_text, callback_data=action_callback)],
        [InlineKeyboardButton(text="🔙 وسائل الدفع", callback_data="admin_payment_methods")],
        [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
    ])


def _normalize_address(value: str) -> str:
    value = (value or "").strip()
    for prefix in ("shamcash:", "shamcash://"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):].strip()
            break
    return value


def _decode_qr(payload: bytes) -> str:
    try:
        from pyzbar.pyzbar import decode as qr_decode
        decoded = qr_decode(Image.open(io.BytesIO(payload)))
        if not decoded:
            return ""
        return _normalize_address(decoded[0].data.decode("utf-8", errors="strict"))
    except Exception:
        logger.exception("Failed to decode payment-method QR")
        return ""


def _progress(step: int, title: str, body: str) -> str:
    return f"💳 <b>إعداد وسيلة الدفع</b>\n\n<b>الخطوة {step} من 3</b> — {html.escape(title)}\n\n{body}"


async def _show_payment_methods(target, edit: bool = False):
    pool = await get_pool()
    async with pool.acquire() as conn:
        methods = await conn.fetch(
            """SELECT code, currency, recipient_name, account_identifier, qr_photo_id, enabled
                 FROM payment_methods
                WHERE provider='ShamCash'
                  AND code IN ('shamcash_usd', 'shamcash_new_syp')
                ORDER BY CASE currency WHEN 'USD' THEN 1 ELSE 2 END"""
        )
    text = "💳 <b>وسائل الدفع — ShamCash</b>\n\n"
    for method in methods:
        status = "🟢 فعال" if method["enabled"] else "🔴 معطل"
        recipient = method["recipient_name"] or "غير مضبوط"
        address = method["account_identifier"] or "غير مضبوط"
        qr = "محفوظ" if method["qr_photo_id"] else "غير محفوظ"
        text += (
            f"<b>{method['currency']}</b> — {CURRENCY_META.get(method['currency'], method['currency'])} — {status}\n"
            f"اسم المستلم: <code>{html.escape(recipient)}</code>\n"
            f"عنوان الاستلام: <code>{html.escape(address)}</code>\n"
            f"QR: {qr}\n\n"
        )
    text += "اختر العملة لعرض بياناتها أو إعادة إعدادها."
    keyboard = _methods_keyboard(methods)
    if edit:
        await target.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text == "/payment_methods")
async def payment_methods_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied")
        return
    await _show_payment_methods(message)


@router.callback_query(F.data == "admin_payment_methods")
async def payment_methods_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await _show_payment_methods(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data.regexp(rf"^admin_pm_view_{CANONICAL_CODE_PATTERN}$"))
async def payment_method_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_view_")
    if code not in CANONICAL_CODES:
        await callback.answer("وسيلة الدفع غير صالحة", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        method = await conn.fetchrow(
            "SELECT code, currency, recipient_name, account_identifier, qr_photo_id, enabled FROM payment_methods WHERE code=$1 AND provider='ShamCash'",
            code,
        )
    if not method:
        await callback.answer("وسيلة الدفع غير موجودة", show_alert=True)
        return
    recipient = method["recipient_name"] or "غير مضبوط"
    address = method["account_identifier"] or "غير مضبوط"
    qr = "محفوظ" if method["qr_photo_id"] else "غير محفوظ"
    status = "🟢 فعال" if method["enabled"] else "🔴 معطل"
    text = (
        f"💳 <b>ShamCash {method['currency']}</b>\n\n"
        f"الحالة: {status}\n"
        f"اسم المستلم: <code>{html.escape(recipient)}</code>\n"
        f"عنوان الاستلام: <code>{html.escape(address)}</code>\n"
        f"QR: {qr}\n\n"
        "إعداد هذه الوسيلة يتم في معالج واحد متتابع: الاسم ← العنوان ← QR."
    )
    await callback.message.edit_text(text, reply_markup=_view_keyboard(code, method["enabled"]), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.regexp(rf"^admin_pm_setup_{CANONICAL_CODE_PATTERN}$"))
async def payment_method_setup_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_setup_")
    if code not in CANONICAL_CODES:
        await callback.answer("وسيلة الدفع غير صالحة", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        method = await conn.fetchrow("SELECT currency FROM payment_methods WHERE code=$1 AND provider='ShamCash'", code)
    if not method:
        await callback.answer("وسيلة الدفع غير موجودة", show_alert=True)
        return
    await state.clear()
    await state.update_data(payment_method_code=code, payment_currency=method["currency"])
    await state.set_state(PaymentMethodStates.waiting_recipient_name)
    await callback.message.edit_text(
        _progress(1, "اسم المستلم", "أرسل اسم المستلم الذي سيظهر للعميل كما هو معتمد لحساب ShamCash."),
        reply_markup=_cancel_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.message(PaymentMethodStates.waiting_recipient_name)
async def payment_method_recipient_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    value = (message.text or "").strip()
    if len(value) < 2 or len(value) > 100:
        await message.answer("❌ اسم المستلم يجب أن يكون بين 2 و100 حرف.")
        return
    await state.update_data(recipient_name=value)
    await state.set_state(PaymentMethodStates.waiting_receiving_address)
    await message.answer(_progress(2, "عنوان الاستلام", "أرسل عنوان/رقم حساب ShamCash الذي سيستقبل الدفعة."), reply_markup=_cancel_keyboard(), parse_mode="HTML")


@router.message(PaymentMethodStates.waiting_receiving_address)
async def payment_method_address_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    value = _normalize_address(message.text or "")
    if len(value) < 5 or len(value) > 150:
        await message.answer("❌ عنوان الاستلام يجب أن يكون بين 5 و150 حرفاً.")
        return
    await state.update_data(receiving_address=value)
    await state.set_state(PaymentMethodStates.waiting_qr)
    await message.answer(_progress(3, "رمز QR", "أرسل الآن صورة QR الخاصة بنفس عنوان الاستلام.\n\nسيتم قراءة العنوان من QR ومقارنته بالعنوان الذي أدخلته قبل الحفظ."), reply_markup=_cancel_keyboard(), parse_mode="HTML")


@router.message(PaymentMethodStates.waiting_qr, F.photo)
async def payment_method_qr_receive(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("⛔ Access denied")
        return
    data = await state.get_data()
    address = _normalize_address(data.get("receiving_address") or "")
    raw = io.BytesIO()
    try:
        await message.bot.download(file=message.photo[-1].file_id, destination=raw)
        payload = raw.getvalue()
        validate_image_payload(payload, file_name="payment-method-qr")
    except ValueError:
        await message.answer("❌ صورة QR غير صالحة أو غير آمنة. أرسل صورة واضحة بصيغة مدعومة.")
        return
    except Exception:
        logger.exception("Failed to download payment-method QR")
        await message.answer("❌ تعذر قراءة صورة QR. أعد إرسالها.")
        return

    qr_address = _decode_qr(payload)
    if not qr_address:
        await message.answer("❌ لم أتمكن من استخراج عنوان ShamCash من QR. أرسل QR صالحاً من التطبيق.")
        return
    if qr_address.casefold() != address.casefold():
        await message.answer(
            "❌ العنوان الموجود داخل QR لا يطابق عنوان الاستلام الذي أدخلته.\n\n"
            f"العنوان المدخل: <code>{html.escape(address)}</code>\n"
            f"العنوان من QR: <code>{html.escape(qr_address)}</code>\n\nأعد إرسال QR المطابق.",
            parse_mode="HTML",
        )
        return

    await state.update_data(qr_photo_id=message.photo[-1].file_id)
    data = await state.get_data()
    await state.set_state(PaymentMethodStates.waiting_confirmation)
    text = (
        "💳 <b>مراجعة بيانات وسيلة الدفع</b>\n\n"
        f"العملة: <b>{html.escape(data['payment_currency'])}</b>\n"
        f"اسم المستلم: <code>{html.escape(data['recipient_name'])}</code>\n"
        f"عنوان الاستلام: <code>{html.escape(data['receiving_address'])}</code>\n"
        "QR: ✅ تم التحقق من مطابقته للعنوان\n\nهل تريد حفظ هذه البيانات؟"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ حفظ", callback_data="admin_pm_setup_confirm")],
        [InlineKeyboardButton(text="🔄 إعادة الإعداد", callback_data=f"admin_pm_setup_{data['payment_method_code']}")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_payment_methods")],
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(PaymentMethodStates.waiting_qr)
async def payment_method_qr_invalid(message: Message):
    if is_admin(message.from_user.id):
        await message.answer("❌ أرسل صورة QR كصورة، وليس كنص أو ملف آخر.")


@router.callback_query(PaymentMethodStates.waiting_confirmation, F.data == "admin_pm_setup_confirm")
async def payment_method_setup_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await state.clear()
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    data = await state.get_data()
    code = data.get("payment_method_code")
    if code not in CANONICAL_CODES or not data.get("qr_photo_id"):
        await state.clear()
        await callback.answer("❌ بيانات الإعداد غير صالحة", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE payment_methods SET recipient_name=$1, account_identifier=$2, qr_photo_id=$3, updated_at=NOW()
               WHERE code=$4 AND provider='ShamCash' RETURNING currency, enabled""",
            data["recipient_name"], data["receiving_address"], data["qr_photo_id"], code,
        )
        if not row:
            await state.clear()
            await callback.answer("❌ وسيلة الدفع غير موجودة", show_alert=True)
            return
        await conn.execute(
            """INSERT INTO audit_logs (admin_id, action, details, new_value, severity)
               VALUES ($1, 'payment_method_setup_completed', $2, $3, 'info')""",
            callback.from_user.id, f"payment_method={code}; currency={row['currency']}; qr_address_verified=true", data["receiving_address"],
        )
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>وسيلة الدفع {row['currency']} جاهزة.</b>\n\nتم حفظ اسم المستلم وعنوان الاستلام وQR بعد التحقق من تطابقهما.",
        parse_mode="HTML", reply_markup=_view_keyboard(code, row["enabled"]),
    )
    await callback.answer("تم الحفظ")


async def _set_payment_method_enabled(callback: CallbackQuery, code: str, enabled: bool, audit_action: str | None = None):
    if code not in CANONICAL_CODES:
        await callback.answer("وسيلة الدفع غير صالحة", show_alert=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        method = await conn.fetchrow(
            """SELECT currency, recipient_name, account_identifier, qr_photo_id, enabled
                 FROM payment_methods
                WHERE code=$1 AND provider='ShamCash'
                FOR UPDATE""",
            code,
        )
        if not method:
            await callback.answer("وسيلة الدفع غير موجودة", show_alert=True)
            return

        if enabled:
            missing = []
            if not method["recipient_name"]:
                missing.append("اسم المستلم")
            if not method["account_identifier"]:
                missing.append("عنوان الاستلام")
            if not method["qr_photo_id"]:
                missing.append("QR")
            if missing:
                await callback.answer(
                    "لا يمكن تفعيل وسيلة الدفع قبل إكمال إعدادها: " + "، ".join(missing),
                    show_alert=True,
                )
                return

        if method["enabled"] != enabled:
            await conn.execute(
                "UPDATE payment_methods SET enabled=$1, updated_at=NOW() WHERE code=$2 AND provider='ShamCash'",
                enabled,
                code,
            )
            action = audit_action or ("payment_method_enable" if enabled else "payment_method_disable")
            await conn.execute(
                """INSERT INTO audit_logs (admin_id, action, details, new_value, severity)
                   VALUES ($1, $2, $3, $4, 'info')""",
                callback.from_user.id,
                action,
                f"payment_method={code}",
                str(enabled),
            )

    recipient = method["recipient_name"] or "غير مضبوط"
    address = method["account_identifier"] or "غير مضبوط"
    qr = "محفوظ" if method["qr_photo_id"] else "غير محفوظ"
    status = "🟢 فعال" if enabled else "🔴 معطل"
    text = (
        f"💳 <b>ShamCash {method['currency']}</b>\n\n"
        f"الحالة: {status}\n"
        f"اسم المستلم: <code>{html.escape(recipient)}</code>\n"
        f"عنوان الاستلام: <code>{html.escape(address)}</code>\n"
        f"QR: {qr}\n\n"
        "إعداد هذه الوسيلة يتم في معالج واحد متتابع: الاسم ← العنوان ← QR."
    )
    await callback.message.edit_text(text, reply_markup=_view_keyboard(code, enabled), parse_mode="HTML")
    await callback.answer("تم التفعيل" if enabled else "تم التعطيل")


@router.callback_query(F.data.regexp(rf"^admin_pm_enable_{CANONICAL_CODE_PATTERN}$"))
async def payment_method_enable(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_enable_")
    await _set_payment_method_enabled(callback, code, True)


@router.callback_query(F.data.regexp(rf"^admin_pm_disable_{CANONICAL_CODE_PATTERN}$"))
async def payment_method_disable(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_disable_")
    await _set_payment_method_enabled(callback, code, False)


@router.callback_query(F.data.regexp(rf"^admin_pm_toggle_{CANONICAL_CODE_PATTERN}$"))
async def payment_method_legacy_toggle(callback: CallbackQuery):
    """Compatibility handler for old Telegram messages containing toggle callbacks."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    code = callback.data.removeprefix("admin_pm_toggle_")
    pool = await get_pool()
    async with pool.acquire() as conn:
        method = await conn.fetchrow(
            "SELECT enabled FROM payment_methods WHERE code=$1 AND provider='ShamCash'",
            code,
        )
    if not method:
        await callback.answer("وسيلة الدفع غير موجودة", show_alert=True)
        return
    await _set_payment_method_enabled(callback, code, not method["enabled"], audit_action="payment_method_toggle")
