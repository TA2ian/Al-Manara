"""Reply keyboards for the bot."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def compact_reply_keyboard(lang: str = 'ar') -> ReplyKeyboardMarkup:
    """Compact reply keyboard for quick access."""
    if lang == 'ar':
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="💰 جديد"),
                    KeyboardButton(text="📋 طلباتي"),
                    KeyboardButton(text="⚙️")
                ]
            ],
            resize_keyboard=True,
            is_persistent=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="💰 New"),
                    KeyboardButton(text="📋 Orders"),
                    KeyboardButton(text="⚙️")
                ]
            ],
            resize_keyboard=True,
            is_persistent=True
        )
