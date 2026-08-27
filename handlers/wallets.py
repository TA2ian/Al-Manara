"""Canonical customer wallet registry and verification flow."""
from __future__ import annotations

import io
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from PIL import Image

from database import get_pool
from keyboards.inline import main_menu_inline
from keyboards.reply import compact_reply_keyboard
from keyboards.wallet import SUPPORTED_WALLET_NETWORKS, wallet_network_keyboard
from services.locale_service import locale_service
from services.media_security import validate_image_payload
from services.wallet_validator import WalletValidator
from states import WalletStates

logger = logging.getLogger(__name__)
router = Router()


def _normalize_qr_value(value: str) -> str:
    normalized = (value or "").strip()
    for prefix in (
        "ethereum:", "ethereum://", "arb:", "arbitrum:", "bep20:", "trc20:",
        "ton:", "ton://transfer/", "solana:", "sol:", "usdt:", "shamcash:", "shamcash://",
    ):
        if normalized.lower().startswith(prefix):
            return normalized[len(prefix):].strip()
    return normalized


def _decode_qr(payload: bytes) -> str:
    try:
        from pyzbar.pyzbar import decode as qr_decode
        decoded = qr_decode(Image.open(io.BytesIO(payload)))
        if not decoded:
            return ""
        return decoded[0].data.decode("utf-8", errors="strict").strip()
    except Exception:
        logger.exception("Failed to decode wallet QR")
        return ""


def _caption_address(caption: str, network: str) -> str:
    candidate = _normalize_qr_value(caption)
    if not candidate:
        return ""
    return candidate if WalletValidator.validate(candidate, network).get("valid") else ""


def _menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إضافة عنوان جديد" if lang == "ar" else "➕ Add new address", callback_data="wallet_add")],
        [InlineKeyboardButton(text="🔙 رجوع" if lang == "ar" else "🔙 Back", callback_data="wallet_back")],
    ])


def _qr_prompt_keyboard(lang: str, allow_skip: bool = True) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📸 متابعة التحقق وإرسال QR" if lang == "ar" else "📸 Continue verification & send QR", callback_data="wallet_qr_continue")]]
    if allow_skip:
        rows.append([InlineKeyboardButton(text="⚠️ تأكيد التخطي" if lang == "ar" else "⚠️ Confirm skip", callback_data="wallet_qr_skip_prompt")])
    rows.append([InlineKeyboardButton(text="❌ إلغاء" if lang == "ar" else "❌ Cancel", callback_data="wallet_qr_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _qr_skip_confirmation_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ نعم، أؤكد التخطي" if lang == "ar" else "⚠️ Yes, confirm skip", callback_data="wallet_qr_skip_confirm")],
        [InlineKeyboardButton(text="📸 متابعة وإرسال QR" if lang == "ar" else "📸 Continue & send QR", callback_data="wallet_qr_continue")],
    ])


def _network_prompt(lang: str, return_to_order: bool) -> str:
    text = (
        "👛 <b>إضافة محفظة استلام</b>\n\n"
        "اختر شبكة USDT التي ينتمي إليها العنوان أولاً. هذا مهم لأن بعض الشبكات تستخدم نفس شكل العنوان.\n\n"
        "بعد اختيار الشبكة يمكنك إرسال <b>العنوان</b>، أو صورة <b>QR</b>، أو مشاركة المحفظة مباشرة من تطبيق محفظتك بحيث يصل <b>العنوان مع QR</b>.\n\n"
        "🔐 سيتحقق البوت من العنوان وفق الشبكة المختارة، ثم يطابقه مع QR قبل اعتماد المحفظة."
        if lang == "ar" else
        "👛 <b>Add receiving wallet</b>\n\n"
        "Select the USDT network first. This matters because some networks use the same address format.\n\n"
        "Then send the <b>address</b>, a <b>QR image</b>, or share the wallet directly from your wallet app so the <b>address and QR</b> arrive together.\n\n"
        "🔐 The bot validates the address for the selected network and matches it with the QR before accepting the wallet."
    )
    if return_to_order:
        text += "\n\n🔒 أثناء إنشاء الطلب يجب أن تكون المحفظة موثقة بـQR مطابق، ولا يمكن تخطي التحقق." if lang == "ar" else "\n\n🔒 During order creation, the wallet must be verified with a matching QR and verification cannot be skipped."
    return text


async def _user(telegram_id: int):
    pool = await get_pool()
    if pool is None:
        return None
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT id, language FROM users WHERE telegram_id = $1", telegram_id)


async def _begin_registration(target: Message | CallbackQuery, state: FSMContext, lang: str, return_to_order: bool) -> None:
    await state.clear()
    await state.update_data(return_to_order=return_to_order)
    await state.set_state(WalletStates.waiting_network)
    text = _network_prompt(lang, return_to_order)
    markup = wallet_network_keyboard(lang, cancel_callback="cancel_order" if return_to_order else "wallet_back")
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "menu_wallets")
async def show_wallets(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    await state.clear()
    lang = user["language"] or "ar"
    pool = await get_pool()
    if pool is None:
        await callback.answer("❌ قاعدة البيانات غير متاحة حالياً", show_alert=True)
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, address, network, label, is_default
               FROM saved_addresses
               WHERE user_id = $1 AND deleted_at IS NULL
                 AND verification_status = 'verified' AND qr_photo_id IS NOT NULL
               ORDER BY network, is_default DESC, created_at DESC""",
            user["id"],
        )
    if not rows:
        await callback.message.edit_text(
            "👛 <b>محافظي</b>\n\nلا توجد عناوين موثقة بعد." if lang == "ar" else "👛 <b>My Wallets</b>\n\nNo verified addresses yet.",
            reply_markup=_menu(lang), parse_mode="HTML",
        )
        await callback.answer()
        return
    lines = ["👛 <b>محافظي</b>\n" if lang == "ar" else "👛 <b>My Wallets</b>\n"]
    buttons = []
    icons = {"BEP20": "🟡", "TRC20": "🔷", "TON": "💎", "ARB": "🔵", "SOLANA": "🟣", "ETH": "⚪"}
    for row in rows:
        label = row["label"] or ("بدون اسم" if lang == "ar" else "Unnamed")
        icon = icons.get(row["network"], "🌐")
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
    await _begin_registration(callback, state, lang, return_to_order=False)


@router.callback_query(WalletStates.waiting_network, F.data.startswith("wallet_network_"))
async def select_wallet_network(callback: CallbackQuery, state: FSMContext):
    network = callback.data.removeprefix("wallet_network_").upper()
    if network not in SUPPORTED_WALLET_NETWORKS:
        await callback.answer("❌ شبكة غير مدعومة", show_alert=True)
        return
    data = await state.get_data()
    return_to_order = bool(data.get("return_to_order"))
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await state.update_data(network=network)
    await state.set_state(WalletStates.waiting_address)
    await callback.message.edit_text(
        (
            f"🌐 <b>الشبكة المختارة: {network}</b>\n\n"
            "أرسل <b>العنوان</b>، أو صورة <b>QR</b>، أو شارك المحفظة مباشرة من تطبيق محفظتك.\n\n"
            "سيتم التحقق من العنوان وفق هذه الشبكة ومطابقته مع QR قبل اعتماده."
        ) if lang == "ar" else (
            f"🌐 <b>Selected network: {network}</b>\n\n"
            "Send the <b>address</b>, a <b>QR image</b>, or share the wallet directly from your wallet app.\n\n"
            "The address will be validated for this network and matched with the QR before acceptance."
        ),
        parse_mode="HTML",
    )
    await callback.answer()


async def _process_qr_first(message: Message, state: FSMContext, payload: bytes, photo_id: str) -> None:
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    data = await state.get_data()
    network = data.get("network")
    if network not in SUPPORTED_WALLET_NETWORKS:
        await state.clear()
        await message.answer("❌ لم يتم اختيار شبكة للمحفظة. ابدأ إضافة المحفظة من جديد." if lang == "ar" else "❌ No wallet network was selected. Start wallet registration again.")
        return
    raw_value = _decode_qr(payload)
    qr_address = _normalize_qr_value(raw_value)
    validation = WalletValidator.validate(qr_address, network)
    if not validation.get("valid"):
        await message.answer(
            f"❌ لم أتمكن من التحقق من عنوان {network} صالح داخل QR. أرسل QR أوضح أو أرسل العنوان كنص." if lang == "ar" else
            f"❌ I could not verify a valid {network} address in this QR. Send a clearer QR or send the address as text."
        )
        return
    caption = message.caption or ""
    if caption:
        caption_address = _caption_address(caption, network)
        if not caption_address:
            await message.answer("❌ العنوان المرفق لا يطابق صيغة الشبكة المختارة." if lang == "ar" else "❌ The attached address does not match the selected network format.")
            return
        if caption_address.casefold() != qr_address.casefold():
            await message.answer("❌ العنوان المرفق مع QR لا يطابق العنوان الموجود داخل QR." if lang == "ar" else "❌ The attached address does not match the address encoded in the QR.")
            return
    await state.update_data(wallet_address=qr_address, wallet_qr_photo_id=photo_id, wallet_qr_first=True)
    await state.set_state(WalletStates.waiting_label)
    await message.answer(
        f"✅ <b>تم التحقق من المحفظة عبر QR</b>\n\n🌐 الشبكة: <b>{network}</b>\n📍 العنوان: <code>{qr_address}</code>\n\nأرسل الآن اسماً لهذه المحفظة لحفظها." if lang == "ar" else
        f"✅ <b>Wallet verified from QR</b>\n\n🌐 Network: <b>{network}</b>\n📍 Address: <code>{qr_address}</code>\n\nSend a label to save this wallet.",
        parse_mode="HTML",
    )


@router.message(WalletStates.waiting_address, F.photo)
async def wallet_qr_first(message: Message, state: FSMContext):
    raw = io.BytesIO()
    try:
        await message.bot.download(file=message.photo[-1].file_id, destination=raw)
        payload = raw.getvalue()
        validate_image_payload(payload, file_name="telegram-photo")
    except ValueError:
        await message.answer("❌ صورة QR غير صالحة أو غير آمنة. أرسل صورة QR واضحة بصيغة مدعومة.")
        return
    except Exception:
        logger.exception("Failed to process wallet QR")
        await message.answer("❌ تعذر معالجة صورة QR. أعد إرسالها من فضلك.")
        return
    await _process_qr_first(message, state, payload, message.photo[-1].file_id)


@router.message(WalletStates.waiting_address)
async def wallet_address(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    data = await state.get_data()
    network = data.get("network")
    address = (message.text or "").strip()
    validation = WalletValidator.validate(address, network) if network else {"valid": False}
    if not validation.get("valid"):
        await message.answer(
            f"❌ العنوان غير صالح لشبكة {network or 'المختارة'}. تأكد من نسخه بالكامل أو أرسل صورة QR صالحة." if lang == "ar" else
            f"❌ Invalid address for {network or 'the selected network'}. Copy it completely or send a valid QR image."
        )
        return
    await state.update_data(wallet_address=address)
    await state.set_state(WalletStates.waiting_qr)
    await message.answer(
        "📸 <b>أرسل الآن QR لنفس العنوان</b>.\n\nسيستخرج البوت العنوان من QR ويقارنه بالعنوان الذي أرسلته. لا يُقبل QR لعنوان مختلف.\n\n" + ("🔒 أثناء إنشاء الطلب يجب إرسال QR المطابق ولا يمكن تخطي التحقق." if data.get("return_to_order") else "يمكنك إرسال QR الآن للتحقق وحفظ العنوان كمحفظة موثقة.")
        if lang == "ar" else
        "📸 <b>Send the QR for the same address</b>.\n\nThe bot extracts the address from the QR and compares it with the address you sent. A different QR is rejected.\n\n" + ("🔒 During order creation, the matching QR is required and verification cannot be skipped." if data.get("return_to_order") else "Send the QR now to verify and save the address as a verified wallet."),
        reply_markup=_qr_prompt_keyboard(lang, allow_skip=not data.get("return_to_order")), parse_mode="HTML",
    )


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_continue")
async def wallet_qr_continue(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await callback.message.edit_text(
        "📸 أرسل الآن صورة QR لنفس عنوان الاستلام.\n\nسيتم استخراج العنوان من QR ومطابقته مع العنوان الذي أرسلته قبل قبول النتيجة." if lang == "ar" else
        "📸 Send the QR image for the same receiving address.\n\nThe address will be extracted from the QR and matched against the address you entered before acceptance.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_skip_prompt")
async def wallet_qr_skip_prompt(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    if data.get("return_to_order"):
        await callback.answer("❌ لا يمكن تخطي التحقق أثناء إنشاء الطلب." if lang == "ar" else "❌ Verification cannot be skipped during order creation.", show_alert=True)
        return
    await callback.message.edit_text(
        "⚠️ <b>تنبيه مهم قبل تخطي QR</b>\n\nإذا تخطيت QR فلن تُحفظ المحفظة كعنوان موثق." if lang == "ar" else
        "⚠️ <b>Important warning before skipping QR</b>\n\nIf you skip QR, the wallet will not be saved as verified.",
        reply_markup=_qr_skip_confirmation_keyboard(lang), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(WalletStates.waiting_qr, F.data == "wallet_qr_skip_confirm")
async def wallet_qr_skip_confirm(callback: CallbackQuery, state: FSMContext):
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    data = await state.get_data()
    if data.get("return_to_order"):
        await callback.answer("❌ لا يمكن تخطي التحقق أثناء إنشاء الطلب." if lang == "ar" else "❌ Verification cannot be skipped during order creation.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "⚠️ تم تأكيد التخطي، لكن لم يتم حفظ المحفظة لأنها غير موثقة بـQR. أعد الإضافة وأرسل QR المطابق إذا أردت حفظها." if lang == "ar" else
        "⚠️ Skip confirmed, but the wallet was not saved because it is not QR-verified. Add it again with the matching QR to save it.",
        reply_markup=_menu(lang), parse_mode="HTML",
    )
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
    address = data.get("wallet_address")
    network = data.get("network")
    if not address or network not in SUPPORTED_WALLET_NETWORKS:
        await state.clear()
        await message.answer("❌ انتهت جلسة إضافة المحفظة. ابدأ الإضافة من جديد." if lang == "ar" else "❌ The wallet registration session expired. Start again.")
        return
    raw = io.BytesIO()
    try:
        await message.bot.download(file=message.photo[-1].file_id, destination=raw)
        payload = raw.getvalue()
        validate_image_payload(payload, file_name="telegram-photo")
        normalized = _normalize_qr_value(_decode_qr(payload))
    except ValueError:
        await message.answer("❌ صورة QR غير صالحة أو غير آمنة. أرسل صورة QR واضحة.")
        return
    except Exception:
        logger.exception("Failed to process wallet QR")
        await message.answer("❌ تعذر معالجة QR. أعد إرسال الصورة بوضوح.")
        return
    if not WalletValidator.validate(normalized, network).get("valid") or normalized.casefold() != address.casefold():
        await message.answer("❌ QR لا يطابق العنوان المدخل على الشبكة المختارة. أرسل QR المطابق لنفس العنوان.")
        return
    await state.update_data(wallet_qr_photo_id=message.photo[-1].file_id)
    await state.set_state(WalletStates.waiting_label)
    await message.answer("🏷️ أرسل اسماً لهذا العنوان، مثل: Binance أو محفظتي الرئيسية." if lang == "ar" else "🏷️ Send a label for this address, e.g. Binance or Main Wallet.")


@router.message(WalletStates.waiting_qr)
async def wallet_qr_required(message: Message):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await message.answer("📸 أرسل صورة QR لنفس العنوان، أو استخدم زر <b>تأكيد التخطي</b> بعد قراءة التنبيه." if lang == "ar" else "📸 Send the QR image for the same address, or use <b>Confirm skip</b> after reading the warning.", reply_markup=_qr_prompt_keyboard(lang), parse_mode="HTML")


@router.message(WalletStates.waiting_label)
async def wallet_label(message: Message, state: FSMContext):
    user = await _user(message.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    if not user:
        await state.clear()
        await message.answer("❌ المستخدم غير موجود.")
        return
    label = (message.text or "").strip()[:64]
    if not label:
        await message.answer("❌ الاسم مطلوب." if lang == "ar" else "❌ A label is required.")
        return
    data = await state.get_data()
    if not data.get("wallet_address") or data.get("network") not in SUPPORTED_WALLET_NETWORKS or not data.get("wallet_qr_photo_id"):
        await state.clear()
        await message.answer("❌ بيانات المحفظة غير مكتملة. أعد الإضافة من البداية." if lang == "ar" else "❌ Wallet registration data is incomplete. Start again.")
        return
    pool = await get_pool()
    if pool is None:
        await message.answer("❌ قاعدة البيانات غير متاحة حالياً. حاول لاحقاً." if lang == "ar" else "❌ Database unavailable. Please try later.")
        return
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT id FROM saved_addresses WHERE user_id=$1 AND address=$2 AND network=$3 AND deleted_at IS NULL", user["id"], data["wallet_address"], data["network"])
            if existing:
                await message.answer("❌ هذا العنوان موجود بالفعل على هذه الشبكة. احذفه ثم أضفه من جديد." if lang == "ar" else "❌ This address already exists on this network. Delete it first, then add it again.")
                await state.clear()
                return
            count = await conn.fetchval("SELECT COUNT(*) FROM saved_addresses WHERE user_id=$1 AND deleted_at IS NULL", user["id"])
            row = await conn.fetchrow(
                """INSERT INTO saved_addresses(user_id,address,network,label,is_default,verification_status,qr_photo_id)
                   VALUES($1,$2,$3,$4,$5,'verified',$6) RETURNING id""",
                user["id"], data["wallet_address"], data["network"], label, count == 0, data["wallet_qr_photo_id"],
            )
    except Exception:
        logger.exception("Failed to save verified wallet for user %s", message.from_user.id)
        await message.answer("❌ تعذر حفظ المحفظة حالياً. حاول مرة أخرى لاحقاً." if lang == "ar" else "❌ The wallet could not be saved right now. Please try again later.")
        return

    return_to_order = bool(data.get("return_to_order"))
    await state.clear()
    text = (
        "✅ تم حفظ المحفظة والتحقق منها. سيتم استخدامها تلقائياً في هذا الطلب والطلبات القادمة." if return_to_order and lang == "ar" else
        "✅ تم حفظ المحفظة والتحقق منها بنجاح." if lang == "ar" else
        "✅ Wallet saved and verified. It will be reused automatically for this order and future orders." if return_to_order else
        "✅ Wallet saved and verified successfully."
    )
    await message.answer(text, reply_markup=_menu(lang))
    if return_to_order:
        from handlers.order_amount_policy import resume_order_after_wallet
        await resume_order_after_wallet(message, state, row["id"])


@router.callback_query(F.data.startswith("wallet_delete_"))
async def wallet_delete(callback: CallbackQuery):
    user = await _user(callback.from_user.id)
    if not user:
        await callback.answer("❌ المستخدم غير موجود", show_alert=True)
        return
    try:
        address_id = int(callback.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ طلب غير صالح", show_alert=True)
        return
    pool = await get_pool()
    if pool is None:
        await callback.answer("❌ قاعدة البيانات غير متاحة", show_alert=True)
        return
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id,is_default FROM saved_addresses WHERE id=$1 AND user_id=$2 AND deleted_at IS NULL", address_id, user["id"])
        if not row:
            await callback.answer("❌ العنوان غير موجود", show_alert=True)
            return
        await conn.execute("UPDATE saved_addresses SET deleted_at=NOW(), is_default=FALSE WHERE id=$1 AND user_id=$2", address_id, user["id"])
        if row["is_default"]:
            replacement = await conn.fetchrow("""SELECT id FROM saved_addresses WHERE user_id=$1 AND deleted_at IS NULL AND verification_status='verified' AND qr_photo_id IS NOT NULL ORDER BY created_at DESC LIMIT 1""", user["id"])
            if replacement:
                await conn.execute("UPDATE saved_addresses SET is_default=TRUE WHERE id=$1", replacement["id"])
    await callback.answer("✅ تم حذف العنوان" if (user["language"] or "ar") == "ar" else "✅ Address deleted", show_alert=True)


@router.callback_query(F.data == "wallet_back")
async def wallet_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await _user(callback.from_user.id)
    lang = (user["language"] or "ar") if user else "ar"
    await callback.message.edit_text(locale_service.get("main_menu", lang), reply_markup=main_menu_inline(lang))
    await callback.message.answer("👇", reply_markup=compact_reply_keyboard(lang))
    await callback.answer()
