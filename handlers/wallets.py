"""Customer wallet registry: verify, label, lock, and delete addresses."""
import io
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from PIL import Image

from states import WalletStates
from services.wallet_validator import WalletValidator

router = Router()


async def _user(telegram_id: int):
    from database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT id, language FROM users WHERE telegram_id = $1", telegram_id)


def _menu(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إضافة عنوان جديد" if lang == "ar" else "➕ Add new address", callback_data="wallet_add")],
        [InlineKeyboardButton(text="🔙 رجوع" if lang == "ar" else "🔙 Back", callback_data="wallet_back")],
    ])


def _qr_prompt_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 متابعة التحقق وإرسال QR" if lang == "ar" else "📸 Continue verification & send QR", callback_data="wallet_qr_continue")],
        [InlineKeyboardButton(text="⚠️ تأكيد التخطي" if lang == "ar" else "⚠️ Confirm skip", callback_data="wallet_qr_skip_prompt")],
        [InlineKeyboardButton(text="❌ إلغاء" if lang == "ar" else "❌ Cancel", callback_data="wallet_qr_cancel")],
    ])


def _qr_skip_confirmation_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ نعم، أؤكد التخطي" if lang == "ar" else "⚠️ Yes, confirm skip", callback_data="wallet_qr_skip_confirm")],
        [InlineKeyboardButton(text="📸 متابعة وإرسال QR" if lang == "ar" else "📸 Continue & send QR", callback_data="wallet_qr_continue")],
    ])


@router.callback_query(F.data == "menu_wallets")
async def show_wallets(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    if not user:
        await callback.answer("❌ User not found", show_alert=True)
        return
    await state.clear()
    lang = user["language"] or "ar"
    from database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, address, network, label, is_default, verification_status
            FROM saved_addresses
            WHERE user_id = $1 AND deleted_at IS NULL AND verification_status = 'verified'
            ORDER BY network, is_default DESC, created_at DESC
        """, user["id"])

    if not rows:
        text = "👛 <b>محافظي</b>\n\nلا توجد عناوين موثقة بعد." if lang == "ar" else "👛 <b>My Wallets</b>\n\nNo verified addresses yet."
        await callback.message.edit_text(text, reply_markup=_menu(lang), parse_mode="HTML")
        await callback.answer()
        return

    lines = ["👛 <b>محافظي</b>\n" if lang == "ar" else "👛 <b>My Wallets</b>\n"]
    buttons = []
    for row in rows:
        label = row["label"] or ("بدون اسم" if lang == "ar" else "Unnamed")
        icon = "🟡" if row["network"] == "BEP20" else "🔷"
        star = " ⭐" if row["is_default"] else ""
        lines.append(f"{icon} <b>{label}</b>{star}\n{row['network']} · <code>{row['address']}</code>\n🟢 موثق\n")
        buttons.append([InlineKeyboardButton(text=f"🗑 حذف {label}", callback_data=f"wallet_delete_{row['id']}")])
    buttons.extend(_menu(lang).inline_keyboard)
    await callback.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "wallet_add")
async def wallet_add(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        "➕ <b>إضافة عنوان استلام</b>\n\nأرسل عنوان BEP20 أو TRC20.\n\n🔒 بعد التحقق لا يمكن تعديل العنوان. التغيير يكون بالحذف ثم إضافة عنوان جديد.\n📸 مطابقة QR مع العنوان مطلوبة للتحقق الكامل. يمكن طلب تخطيها فقط بعد قراءة تنبيه المسؤولية." if lang == "ar" else
        "➕ <b>Add receiving address</b>\n\nSend a BEP20 or TRC20 address.\n\n🔒 A verified address cannot be edited. Changes require delete + add.\n📸 QR/address matching is required for full verification. Skipping is available only after reading the responsibility warning.",
        parse_mode="HTML")
    await callback.answer()


@router.message(WalletStates.waiting_address)
async def wallet_address(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    address = (message.text or "").replace(" ", "").strip()
    network = WalletValidator.detect_network(address)
    validation = WalletValidator.validate(address, network) if network else {"valid": False}
    if not validation["valid"]:
        await message.answer("❌ العنوان غير صالح لـBEP20/TRC20. تأكد من نسخه بالكامل." if lang == "ar" else "❌ Invalid BEP20/TRC20 address. Copy the full address.")
        return
    await state.update_data(wallet_address=address, network=network)
    await state.set_state(WalletStates.waiting_qr)
    await message.answer(
        "📸 <b>الخطوة الأخيرة للتحقق من المحفظة</b>\n\nأرسل صورة QR لنفس عنوان الاستلام.\n\n🔐 مطابقة QR مع العنوان تساعدنا على تقليل أخطاء النسخ والتحقق من العنوان قبل استخدامه في الطلب.\n\nإذا لم ترسل QR، سيظهر لك تنبيه يوضح مسؤوليتك قبل أن تتمكن من تأكيد التخطي." if lang == "ar" else
        "📸 <b>Final wallet verification step</b>\n\nSend a QR image for the same receiving address.\n\n🔐 Matching the QR to the address helps reduce copying errors and verify the address before it is used in an order.\n\nIf you do not send a QR, you will see a responsibility warning before you can confirm the skip.",
        reply_markup=_qr_prompt_keyboard(lang),
        parse_mode="HTML"
    )


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_continue")
async def wallet_qr_continue(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await callback.message.edit_text(
        "📸 أرسل الآن صورة QR لنفس عنوان الاستلام.\n\nسيتم استخراج العنوان من QR ومطابقته مع العنوان الذي أرسلته قبل قبول النتيجة." if lang == "ar" else
        "📸 Send the QR image for the same receiving address.\n\nThe address will be extracted from the QR and matched against the address you entered before the result is accepted.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_skip_prompt")
async def wallet_qr_skip_prompt(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    text = (
        "⚠️ <b>تنبيه مهم قبل تخطي QR</b>\n\n"
        "تنص شروط الخدمة على أن <b>أنت وحدك المسؤول عن صحة عنوان محفظة USDT الذي تُدخله</b>، وأننا <b>غير مسؤولين عن فقدان الأموال نتيجة إدخال عنوان خاطئ أو اختيار شبكة غير صحيحة</b>.\n\n"
        "يساعدك البوت على تقليل الأخطاء من خلال التحقق من العنوان والتعرف على الشبكة، كما أن إرسال QR لنفس العنوان يضيف خطوة تحقق إضافية ويقلل احتمال الخطأ.\n\n"
        "🔐 <b>نوصي بشدة بإرسال QR</b> لنفس عنوان الاستلام لضمان التحقق بأمان قبل متابعة الطلب.\n\n"
        "إذا اخترت التخطي، فأنت تؤكد أنك راجعت العنوان والشبكة بنفسك وتتحمل مسؤولية صحة بيانات الاستلام."
    ) if lang == "ar" else (
        "⚠️ <b>Important warning before skipping QR</b>\n\n"
        "Our terms state that <b>you are solely responsible for the correctness of the USDT wallet address you enter</b>, and that <b>we are not responsible for loss of funds caused by entering an incorrect address or selecting an incorrect network</b>.\n\n"
        "The bot helps reduce mistakes by validating the address and detecting the network. Sending a QR for the same address adds another verification step and further reduces the risk of error.\n\n"
        "🔐 <b>We strongly recommend sending the QR</b> for the same receiving address so it can be verified safely before continuing.\n\n"
        "If you choose to skip, you confirm that you have reviewed the address and network yourself and accept responsibility for the receiving details."
    )
    await callback.message.edit_text(text, reply_markup=_qr_skip_confirmation_keyboard(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_skip_confirm")
async def wallet_qr_skip_confirm(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    data = await state.get_data()
    if not data.get("return_to_order"):
        await callback.message.edit_text(
            "⚠️ تم تأكيد التخطي، لكن لم يتم حفظ المحفظة في محافظي لأنها غير موثقة بـQR. إذا أردت حفظها وإعادة استخدامها، أعد الإضافة وأرسل QR المطابق." if lang == "ar" else
            "⚠️ Skip confirmed, but the wallet was not saved to My Wallets because it is not fully verified with a QR. To save and reuse it, add it again and provide the matching QR.",
            reply_markup=_menu(lang),
            parse_mode="HTML"
        )
        await state.clear()
        await callback.answer()
        return

    # Skipping QR is allowed only after the explicit responsibility confirmation.
    address = data.get("wallet_address")
    network = data.get("network")
    await state.clear()
    await state.update_data(
        wallet_address=address,
        network=network,
        wallet_qr_photo_id=None,
        address_from_saved=False,
        wallet_qr_skipped=True,
    )
    from handlers.order_wallet_policy import _continue_to_currency
    await callback.message.edit_text(
        "⚠️ تم تأكيد تخطي QR. سيتم استخدام عنوان المحفظة الذي تحققت منه أنت فقط لهذا الطلب.\n\n💱 اختر الآن عملة الدفع." if lang == "ar" else
        "⚠️ QR skip confirmed. Only the wallet address you reviewed will be used for this order.\n\n💱 Now choose the payment currency.",
        parse_mode="HTML"
    )
    await _continue_to_currency(callback.message, state, lang)
    await callback.answer()


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_cancel")
async def wallet_qr_cancel(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await state.clear()
    await callback.message.edit_text("❌ تم إلغاء إضافة المحفظة." if lang == "ar" else "❌ Wallet registration cancelled.")
    await callback.answer()


@router.message(WalletStates.waiting_qr, F.photo)
async def wallet_qr(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    data = await state.get_data()
    address = data["wallet_address"]
    raw = io.BytesIO()
    await message.bot.download(file=message.photo[-1].file_id, destination=raw)
    raw.seek(0)
    try:
        # QR decoding is an optional native dependency at process startup; load
        # it only when an actual QR image is submitted so the bot can start and
        # serve non-QR flows even if the host is temporarily missing zbar.
        from pyzbar.pyzbar import decode as qr_decode
        decoded = qr_decode(Image.open(raw))
        qr_text = decoded[0].data.decode("utf-8").strip() if decoded else ""
    except Exception:
        qr_text = ""
    if not qr_text:
        await message.answer("❌ لم أتمكن من قراءة QR. أرسل صورة أوضح." if lang == "ar" else "❌ QR could not be read. Send a clearer image.")
        return
    normalized = qr_text
    for prefix in ("ethereum:", "tron:", "trc20:", "bep20:", "usdt:"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    if normalized.lower() != address.lower():
        await message.answer("❌ QR لا يطابق العنوان المدخل. أرسل QR المطابق لنفس العنوان." if lang == "ar" else "❌ QR does not match the entered address. Send the matching QR.")
        return
    await state.update_data(wallet_qr_photo_id=message.photo[-1].file_id)
    await state.set_state(WalletStates.waiting_label)
    await message.answer("🏷️ أرسل اسماً لهذا العنوان، مثل: Binance أو محفظتي الرئيسية." if lang == "ar" else "🏷️ Send a label for this address, e.g. Binance or Main Wallet.")


@router.message(WalletStates.waiting_qr)
async def wallet_qr_required(message: Message):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await message.answer(
        "📸 أرسل صورة QR لنفس العنوان، أو استخدم زر <b>تأكيد التخطي</b> بعد قراءة تنبيه المسؤولية." if lang == "ar" else
        "📸 Send the QR image for the same address, or use <b>Confirm skip</b> after reading the responsibility warning.",
        reply_markup=_qr_prompt_keyboard(lang),
        parse_mode="HTML"
    )


@router.message(WalletStates.waiting_label)
async def wallet_label(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    label = (message.text or "").strip()[:64]
    if not label:
        await message.answer("❌ الاسم مطلوب." if lang == "ar" else "❌ A label is required.")
