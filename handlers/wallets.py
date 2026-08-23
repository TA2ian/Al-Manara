"""Authoritative customer wallet registry flow."""
import io

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from PIL import Image

from states import WalletStates
from services.wallet_validator import WalletValidator

router = Router()


def _normalize_qr_value(value: str) -> str:
    normalized = (value or "").strip()
    for prefix in ("ethereum:", "tron:", "trc20:", "bep20:", "usdt:"):
        if normalized.lower().startswith(prefix):
            return normalized[len(prefix):].strip()
    return normalized


async def _user(telegram_id: int):
    from database import get_pool
    pool = await get_pool()
    if pool is None:
        return None
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1",
            telegram_id,
        )


def _menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ إضافة عنوان جديد" if lang == "ar" else "➕ Add new address",
            callback_data="wallet_add",
        )],
        [InlineKeyboardButton(
            text="🔙 رجوع" if lang == "ar" else "🔙 Back",
            callback_data="wallet_back",
        )],
    ])


def _qr_prompt_keyboard(lang: str, allow_skip: bool = True) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(
        text="📸 متابعة التحقق وإرسال QR" if lang == "ar" else "📸 Continue verification & send QR",
        callback_data="wallet_qr_continue",
    )]]
    if allow_skip:
        buttons.append([InlineKeyboardButton(
            text="⚠️ تأكيد التخطي" if lang == "ar" else "⚠️ Confirm skip",
            callback_data="wallet_qr_skip_prompt",
        )])
    buttons.append([InlineKeyboardButton(
        text="❌ إلغاء" if lang == "ar" else "❌ Cancel",
        callback_data="wallet_qr_cancel",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _qr_skip_confirmation_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚠️ نعم، أؤكد التخطي" if lang == "ar" else "⚠️ Yes, confirm skip",
            callback_data="wallet_qr_skip_confirm",
        )],
        [InlineKeyboardButton(
            text="📸 متابعة وإرسال QR" if lang == "ar" else "📸 Continue & send QR",
            callback_data="wallet_qr_continue",
        )],
    ])


@router.callback_query(F.data == "menu_wallets")
async def show_wallets(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return

    await state.clear()
    lang = user["language"] or "ar"
    from database import get_pool
    pool = await get_pool()
    if pool is None:
        await callback.answer("❌ قاعدة البيانات غير متاحة حالياً", show_alert=True)
        return

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, address, network, label, is_default, verification_status
               FROM saved_addresses
              WHERE user_id = $1 AND deleted_at IS NULL AND verification_status = 'verified'
              ORDER BY network, is_default DESC, created_at DESC""",
            user["id"],
        )

    if not rows:
        text = (
            "👛 <b>محافظي</b>\n\nلا توجد عناوين موثقة بعد."
            if lang == "ar" else
            "👛 <b>My Wallets</b>\n\nNo verified addresses yet."
        )
        await callback.message.edit_text(text, reply_markup=_menu(lang), parse_mode="HTML")
        await callback.answer()
        return

    lines = ["👛 <b>محافظي</b>\n" if lang == "ar" else "👛 <b>My Wallets</b>\n"]
    buttons = []
    for row in rows:
        label = row["label"] or ("بدون اسم" if lang == "ar" else "Unnamed")
        icon = "🟡" if row["network"] == "BEP20" else "🔷"
        star = " ⭐" if row["is_default"] else ""
        lines.append(
            f"{icon} <b>{label}</b>{star}\n"
            f"{row['network']} · <code>{row['address']}</code>\n"
            "🟢 موثق\n"
        )
        buttons.append([InlineKeyboardButton(
            text=f"🗑 حذف {label}",
            callback_data=f"wallet_delete_{row['id']}",
        )])

    buttons.extend(_menu(lang).inline_keyboard)
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "wallet_add")
async def wallet_add(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await state.set_state(WalletStates.waiting_address)

    text = (
        "➕ <b>إضافة محفظة استلام</b>\n\n"
        "أرسل <b>عنوان المحفظة</b>، أو صورة <b>QR</b>، أو شارك المحفظة مباشرة من تطبيق محفظتك "
        "بحيث يصل <b>العنوان مع QR</b>.\n\n"
        "🔐 سيتحقق البوت من العنوان، يتعرف على الشبكة، ثم يطابق العنوان مع QR قبل اعتماده.\n"
        "يمكنك استخدام <b>BEP20</b> أو <b>TRC20</b>."
        if lang == "ar" else
        "➕ <b>Add receiving wallet</b>\n\n"
        "Send the <b>wallet address</b>, a <b>QR image</b>, or share the wallet directly from your wallet app "
        "so the <b>address and QR</b> arrive together.\n\n"
        "🔐 The bot validates the address, detects the network, and matches the address with the QR before accepting it.\n"
        "You can use <b>BEP20</b> or <b>TRC20</b>."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(WalletStates.waiting_address)
async def wallet_address(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    address = (message.text or "").replace(" ", "").strip()
    network = WalletValidator.detect_network(address)
    validation = WalletValidator.validate(address, network) if network else {"valid": False}
    if not validation.get("valid"):
        await message.answer(
            "❌ العنوان غير صالح لـBEP20/TRC20. تأكد من نسخه بالكامل."
            if lang == "ar" else
            "❌ Invalid BEP20/TRC20 address. Copy the full address."
        )
        return

    data = await state.get_data()
    await state.update_data(wallet_address=address, network=network)
    await state.set_state(WalletStates.waiting_qr)
    await message.answer(
        "📸 <b>أرسل الآن QR لنفس العنوان</b>.\n\n"
        "سيستخرج البوت العنوان من QR ويقارنه حرفياً بالعنوان الذي أرسلته. لا يُقبل QR لعنوان مختلف.\n\n"
        + (
            "🔒 أثناء إنشاء الطلب يجب إرسال QR المطابق ولا يمكن تخطي التحقق."
            if data.get("return_to_order") else
            "يمكنك تأكيد التخطي لاحقاً إذا لم ترد حفظ المحفظة كعنوان موثق."
        )
        if lang == "ar" else
        "📸 <b>Send the QR for the same address</b>.\n\n"
        "The bot extracts the address from the QR and compares it exactly with the address you sent. A different QR is rejected.\n\n"
        + (
            "🔒 During order creation, the matching QR is required and verification cannot be skipped."
            if data.get("return_to_order") else
            "You can confirm the skip later if you do not want to save the wallet as verified."
        ),
        reply_markup=_qr_prompt_keyboard(lang, allow_skip=not data.get("return_to_order")),
        parse_mode="HTML",
    )


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_continue")
async def wallet_qr_continue(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await callback.message.edit_text(
        "📸 أرسل الآن صورة QR لنفس عنوان الاستلام.\n\nسيتم استخراج العنوان من QR ومطابقته مع العنوان الذي أرسلته قبل قبول النتيجة."
        if lang == "ar" else
        "📸 Send the QR image for the same receiving address.\n\nThe address will be extracted from the QR and matched against the address you entered before the result is accepted.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_skip_prompt")
async def wallet_qr_skip_prompt(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    if data.get("return_to_order"):
        await callback.answer(
            "❌ لا يمكن تخطي التحقق أثناء إنشاء الطلب."
            if lang == "ar" else
            "❌ Verification cannot be skipped during order creation.",
            show_alert=True,
        )
        return

    text = (
        "⚠️ <b>تنبيه مهم قبل تخطي QR</b>\n\n"
        "أنت مسؤول عن صحة عنوان المحفظة والشبكة. إرسال QR لنفس العنوان يضيف خطوة تحقق ويقلل احتمال الخطأ.\n\n"
        "إذا اخترت التخطي، فلن تُحفظ المحفظة كعنوان موثق."
        if lang == "ar" else
        "⚠️ <b>Important warning before skipping QR</b>\n\n"
        "You are responsible for the wallet address and network. Sending a QR for the same address adds a verification step and reduces the risk of error.\n\n"
        "If you skip, the wallet will not be saved as verified."
    )
    await callback.message.edit_text(
        text,
        reply_markup=_qr_skip_confirmation_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_skip_confirm")
async def wallet_qr_skip_confirm(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    data = await state.get_data()
    if data.get("return_to_order"):
        await callback.answer(
            "❌ لا يمكن تخطي التحقق أثناء إنشاء الطلب."
            if lang == "ar" else
            "❌ Verification cannot be skipped during order creation.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "⚠️ تم تأكيد التخطي، لكن لم يتم حفظ المحفظة في محافظي لأنها غير موثقة بـQR. إذا أردت حفظها وإعادة استخدامها، أعد الإضافة وأرسل QR المطابق."
        if lang == "ar" else
        "⚠️ Skip confirmed, but the wallet was not saved to My Wallets because it is not verified with a QR. To save and reuse it, add it again and provide the matching QR.",
        reply_markup=_menu(lang),
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_cancel")
async def wallet_qr_cancel(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await state.clear()
    await callback.message.edit_text(
        "❌ تم إلغاء إضافة المحفظة." if lang == "ar" else "❌ Wallet registration cancelled."
    )
    await callback.answer()


@router.message(WalletStates.waiting_qr, F.photo)
async def wallet_qr(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    data = await state.get_data()
    address = data.get("wallet_address")
    if not address:
        await state.clear()
        await message.answer(
            "❌ انتهت جلسة إضافة المحفظة. ابدأ الإضافة من جديد."
            if lang == "ar" else
            "❌ The wallet registration session expired. Start again."
        )
        return

    raw = io.BytesIO()
    try:
        await message.bot.download(file=message.photo[-1].file_id, destination=raw)
        raw.seek(0)
        from pyzbar.pyzbar import decode as qr_decode
        decoded = qr_decode(Image.open(raw))
        qr_text = decoded[0].data.decode("utf-8").strip() if decoded else ""
    except Exception:
        qr_text = ""

    normalized = _normalize_qr_value(qr_text)
    if not normalized:
        await message.answer(
            "❌ لم أتمكن من قراءة QR. أرسل صورة أوضح."
            if lang == "ar" else
            "❌ QR could not be read. Send a clearer image."
        )
        return

    if normalized.lower() != address.lower():
        await message.answer(
            "❌ QR لا يطابق العنوان المدخل. أرسل QR المطابق لنفس العنوان."
            if lang == "ar" else
            "❌ QR does not match the entered address. Send the matching QR."
        )
        return

    await state.update_data(wallet_qr_photo_id=message.photo[-1].file_id)
    await state.set_state(WalletStates.waiting_label)
    await message.answer(
        "🏷️ أرسل اسماً لهذا العنوان، مثل: Binance أو محفظتي الرئيسية."
        if lang == "ar" else
        "🏷️ Send a label for this address, e.g. Binance or Main Wallet."
    )


@router.message(WalletStates.waiting_qr)
async def wallet_qr_required(message: Message):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await message.answer(
        "📸 أرسل صورة QR لنفس العنوان، أو استخدم زر <b>تأكيد التخطي</b> بعد قراءة التنبيه."
        if lang == "ar" else
        "📸 Send the QR image for the same address, or use <b>Confirm skip</b> after reading the warning.",
        reply_markup=_qr_prompt_keyboard(lang),
        parse_mode="HTML",
    )


@router.message(WalletStates.waiting_label)
async def wallet_label(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    if not user:
        await state.clear()
        await message.answer("❌ المستخدم غير موجود." if lang == "ar" else "❌ User not found.")
        return

    label = (message.text or "").strip()[:64]
    if not label:
        await message.answer("❌ الاسم مطلوب." if lang == "ar" else "❌ A label is required.")
        return

    data = await state.get_data()
    if not data.get("wallet_address") or not data.get("network") or not data.get("wallet_qr_photo_id"):
        await message.answer(
            "❌ بيانات المحفظة غير مكتملة. أعد إضافة المحفظة من البداية."
            if lang == "ar" else
            "❌ Wallet registration data is incomplete. Please start wallet registration again."
        )
        await state.clear()
        return

    from database import get_pool
    pool = await get_pool()
    if pool is None:
        await message.answer("❌ قاعدة البيانات غير متاحة حالياً. حاول لاحقاً." if lang == "ar" else "❌ Database unavailable. Try again later.")
        return

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM saved_addresses WHERE user_id=$1 AND address=$2 AND network=$3 AND deleted_at IS NULL",
            user["id"], data["wallet_address"], data["network"],
        )
        if existing:
            await message.answer(
                "❌ هذا العنوان موجود بالفعل. لا يمكن تعديله؛ احذف العنوان الحالي ثم أضفه من جديد."
                if lang == "ar" else
                "❌ This address already exists. It cannot be edited; delete it first and add it again."
            )
            return

        row = await conn.fetchrow(
            """INSERT INTO saved_addresses
               (user_id, address, network, label, qr_photo_id, is_default, verification_status, verified_at)
               VALUES ($1,$2,$3,$4,$5,FALSE,'verified',NOW())
               RETURNING id, address, network, qr_photo_id""",
            user["id"], data["wallet_address"], data["network"], label, data["wallet_qr_photo_id"],
        )

    return_to_order = bool(data.get("return_to_order"))
    order_context = {
        key: data.get(key)
        for key in ("amount_usdt", "order_amount_usdt", "calculation", "payment_currency")
        if data.get(key) is not None
    }
    await state.clear()

    if return_to_order:
        await state.update_data(
            **order_context,
            wallet_address=row["address"],
            network=row["network"],
            wallet_qr_photo_id=row["qr_photo_id"],
            wallet_id=row["id"],
            saved_address_id=row["id"],
            address_from_saved=False,
            wallet_qr_skipped=False,
        )
        await message.answer(
            "✅ تم حفظ المحفظة وQR وتوثيقهما. سيتم استخدامهما تلقائياً في هذا الطلب والطلبات القادمة."
            if lang == "ar" else
            "✅ The wallet and QR were saved and verified. They will be used automatically for this and future orders."
        )
        from handlers.order_wallet_policy import _continue_to_currency
        await _continue_to_currency(message, state, lang)
        return

    await message.answer(
        "✅ تم حفظ العنوان وتوثيقه. 🔒 لا يمكن تعديله؛ يمكن حذفه وإضافة عنوان جديد فقط."
        if lang == "ar" else
        "✅ Address saved and verified. 🔒 It cannot be edited; delete it and add a new address to change it."
    )


@router.callback_query(F.data.startswith("wallet_delete_"))
async def wallet_delete(callback: CallbackQuery):
    user = await _user(callback.from_user.id)
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return

    lang = user["language"] or "ar"
    try:
        wallet_id = int(callback.data.rsplit("_", 1)[1])
    except (AttributeError, ValueError):
        await callback.answer("❌ عنوان غير صالح" if lang == "ar" else "❌ Invalid wallet", show_alert=True)
        return

    from database import get_pool
    pool = await get_pool()
    if pool is None:
        await callback.answer("❌ قاعدة البيانات غير متاحة حالياً", show_alert=True)
        return

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id,address,network,label
               FROM saved_addresses
              WHERE id=$1 AND user_id=$2 AND deleted_at IS NULL AND verification_status='verified'""",
            wallet_id, user["id"],
        )
        if not row:
            await callback.answer("❌ العنوان غير موجود", show_alert=True)
            return

        active = await conn.fetchval(
            """SELECT 1 FROM orders
               WHERE user_id=$1 AND wallet_address=$2 AND network=$3
                 AND status IN ('pending','waiting_payment','receipt_received','payment_confirmed')
               LIMIT 1""",
            user["id"], row["address"], row["network"],
        )
        if active:
            await callback.answer(
                "❌ لا يمكن حذف عنوان مرتبط بطلب نشط."
                if lang == "ar" else
                "❌ This address is linked to an active order.",
                show_alert=True,
            )
            return

        await conn.execute(
            "DELETE FROM saved_addresses WHERE id=$1 AND user_id=$2",
            wallet_id, user["id"],
        )

    await callback.answer("تم حذف العنوان" if lang == "ar" else "Address deleted")
    await callback.message.edit_text(
        "👛 <b>محافظي</b>\n\nتم حذف العنوان. استخدم إضافة عنوان جديد لإضافة بديل."
        if lang == "ar" else
        "👛 <b>My Wallets</b>\n\nAddress deleted. Use Add new address to add a replacement.",
        reply_markup=_menu(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "wallet_back")
async def wallet_back(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await state.clear()
    from keyboards.inline import main_menu_inline
    await callback.message.edit_text(
        "🏠 <b>القائمة الرئيسية</b>" if lang == "ar" else "🏠 <b>Main menu</b>",
        reply_markup=main_menu_inline(lang),
        parse_mode="HTML",
    )
    await callback.answer()
