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
        "solana:", "sol:", "usdt:", "shamcash:", "shamcash://",
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
    icons = {"BEP20": "🟡", "TRC20": "🔷", "ARB": "🔵", "SOLANA": "🟣", "ETH": "⚪", "POLYGON": "🟪"}
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
