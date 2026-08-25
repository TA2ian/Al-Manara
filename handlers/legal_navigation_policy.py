"""Customer-facing legal policy navigation."""
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from services.legal_policy import TERMS_TEXT
from services.locale_service import locale_service

router = Router()

_SECTION_PATTERN = re.compile(r"(?=<b>[1-9]+\.\s)")

_SECTION_TITLES = {
    "ar": [
        "📜 طبيعة الخدمة والحماية",
        "👛 المحفظة وعنوان الاستلام",
        "🔐 التوثيق والخصوصية",
        "💳 الدفع والمعاملات",
        "📦 الطلبات والمعالجة",
        "🛡️ الأمان ومكافحة الاحتيال",
        "🔄 التحديثات والسجلات",
    ],
    "en": [
        "📜 Service & Protection",
        "👛 Wallet & Receiving Address",
        "🔐 Verification & Privacy",
        "💳 Payments & Transactions",
        "📦 Orders & Processing",
        "🛡️ Security & Anti-Fraud",
        "🔄 Updates & Records",
    ],
}


def _sections(lang: str) -> list[str]:
    text = TERMS_TEXT.get(lang, TERMS_TEXT["ar"])
    parts = [part.strip() for part in _SECTION_PATTERN.split(text) if part.strip()]
    return [part for part in parts if re.match(r"<b>[1-9]+\.\s", part)]


def _menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    titles = _SECTION_TITLES.get(lang, _SECTION_TITLES["ar"])
    rows = []
    for index in range(0, len(titles), 2):
        row = [InlineKeyboardButton(text=titles[index], callback_data=f"legal_section_{index + 1}")]
        if index + 1 < len(titles):
            row.append(InlineKeyboardButton(text=titles[index + 1], callback_data=f"legal_section_{index + 2}"))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(
            text="🔙 القائمة الرئيسية" if lang == "ar" else "🔙 Main Menu",
            callback_data="legal_back_main",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _section_keyboard(lang: str, index: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    navigation = []
    if index > 0:
        navigation.append(InlineKeyboardButton(
            text="⬅️ السابق" if lang == "ar" else "⬅️ Previous",
            callback_data=f"legal_section_{index}",
        ))
    if index < total - 1:
        navigation.append(InlineKeyboardButton(
            text="التالي ➡️" if lang == "ar" else "Next ➡️",
            callback_data=f"legal_section_{index + 2}",
        ))
    if navigation:
        rows.append(navigation)
    rows.append([
        InlineKeyboardButton(
            text="📚 الشروط والسياسات" if lang == "ar" else "📚 Terms & Policies",
            callback_data="menu_disclaimer",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "menu_disclaimer")
async def show_legal_sections(callback: CallbackQuery):
    """Show the legal policy index instead of the monolithic message."""
    lang = "ar"
    try:
        user = await _get_user(callback.from_user.id)
        if user:
            lang = user["language"] or "ar"
    except Exception:
        lang = "ar"
    title = (
        "📚 <b>الشروط والسياسات</b>\n\nاختر القسم الذي تريد قراءته. يمكنك التنقل بين الأقسام أو العودة إلى القائمة الرئيسية."
        if lang == "ar" else
        "📚 <b>Terms & Policies</b>\n\nChoose a section. You can move between sections or return to the main menu."
    )
    await callback.message.edit_text(title, reply_markup=_menu_keyboard(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^legal_section_[1-7]$"))
async def show_legal_section(callback: CallbackQuery):
    """Render one legal section with previous/next navigation."""
    lang = "ar"
    try:
        user = await _get_user(callback.from_user.id)
        if user:
            lang = user["language"] or "ar"
    except Exception:
        lang = "ar"

    index = int(callback.data.rsplit("_", 1)[1]) - 1
    sections = _sections(lang)
    if index < 0 or index >= len(sections):
        await callback.answer("❌ القسم غير متوفر" if lang == "ar" else "❌ Section unavailable", show_alert=True)
        return

    await callback.message.edit_text(
        sections[index],
        reply_markup=_section_keyboard(lang, index, len(sections)),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "legal_back_main")
async def legal_back_main(callback: CallbackQuery):
    """Return from the legal index to the normal customer menu."""
    lang = "ar"
    try:
        user = await _get_user(callback.from_user.id)
        if user:
            lang = user["language"] or "ar"
    except Exception:
        lang = "ar"

    from keyboards.inline import main_menu_inline

    await callback.message.edit_text(
        locale_service.get("main_menu", lang),
        reply_markup=main_menu_inline(lang),
        parse_mode="HTML",
    )
    await callback.answer()


async def _get_user(telegram_id: int):
    from database import get_pool

    pool = await get_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1",
            telegram_id,
        )
