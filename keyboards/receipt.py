"""Customer-facing receipt action keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def manual_receipt_review_keyboard(order_id: int, lang: str = "ar") -> InlineKeyboardMarkup:
    """Offer manual admin review only after automatic verification fails."""
    if lang == "en":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📨 Request manual review",
                        callback_data=f"manual_receipt_review_{order_id}",
                    )
                ]
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📨 إرسال للمراجعة اليدوية",
                    callback_data=f"manual_receipt_review_{order_id}",
                )
            ]
        ]
    )
