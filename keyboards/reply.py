"""Reply keyboards for the bot."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def compact_reply_keyboard(lang: str = 'ar') -> ReplyKeyboardMarkup:
    """Compact reply keyboard for quick access."""
    if lang == 'ar':
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="💰 إنشاء طلب شراء"),
                    KeyboardButton(text="📋 طلباتي"),
                    KeyboardButton(text="⚙️ القائمة")
                ]
            ],
            resize_keyboard=True,
            is_persistent=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="💰 Buy Order"),
                    KeyboardButton(text="📋 Orders"),
                    KeyboardButton(text="⚙️ Menu")
                ]
            ],
            resize_keyboard=True,
            is_persistent=True
        )
