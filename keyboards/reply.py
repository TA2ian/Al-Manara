"""Reply keyboards and lifecycle-safe dashboard shortcuts."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def customer_dashboard_keyboard(lang: str = "ar") -> ReplyKeyboardMarkup:
    """Show customer shortcuts only while the customer is at a dashboard boundary."""
    keyboard = (
        [[KeyboardButton(text="💰 إنشاء طلب شراء"), KeyboardButton(text="📋 طلباتي"), KeyboardButton(text="⚙️ القائمة")]]
        if lang == "ar"
        else [[KeyboardButton(text="💰 Buy Order"), KeyboardButton(text="📋 Orders"), KeyboardButton(text="⚙️ Menu")]]
    )
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True, is_persistent=False)


def admin_dashboard_keyboard(lang: str = "ar") -> ReplyKeyboardMarkup:
    """Provide a dedicated admin shortcut without exposing customer actions."""
    text = "👑 لوحة الأدمن" if lang == "ar" else "👑 Admin Dashboard"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        is_persistent=False,
    )


def remove_dashboard_keyboard() -> ReplyKeyboardRemove:
    """Remove any dashboard reply keyboard before entering a multi-step flow."""
    return ReplyKeyboardRemove(remove_keyboard=True)


def compact_reply_keyboard(lang: str = "ar") -> ReplyKeyboardMarkup:
    """Backward-compatible alias for the customer dashboard keyboard."""
    return customer_dashboard_keyboard(lang)


def phone_share_keyboard(lang: str = "ar") -> ReplyKeyboardMarkup:
    """One-time mandatory Telegram contact sharing keyboard."""
    text = "📱 مشاركة رقم الهاتف" if lang == "ar" else "📱 Share phone number"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        is_persistent=False,
        input_field_placeholder="اضغط لمشاركة رقم الهاتف" if lang == "ar" else "Tap to share your phone",
    )
