"""Administrative order action keyboards."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def close_without_fulfillment_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Require explicit confirmation before collecting an administrative close reason."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔒 متابعة الإغلاق الإداري", callback_data=f"admin_close_reason_{order_id}")],
            [InlineKeyboardButton(text="↩️ الرجوع", callback_data=f"admin_close_back_{order_id}")],
        ]
    )


def close_without_fulfillment_confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Require a second explicit confirmation after the admin supplied a reason."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ تأكيد الإغلاق", callback_data=f"admin_close_confirm_{order_id}")],
            [InlineKeyboardButton(text="✏️ تعديل السبب", callback_data=f"admin_close_reason_{order_id}")],
            [InlineKeyboardButton(text="↩️ إلغاء", callback_data=f"admin_close_back_{order_id}")],
        ]
    )


def payment_confirmed_admin_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Offer fulfillment or guarded administrative closure after payment confirmation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 إرسال USDT", callback_data=f"admin_send_usdt_{order_id}"),
                InlineKeyboardButton(text="🔒 إغلاق دون تنفيذ", callback_data=f"admin_close_without_fulfillment_{order_id}"),
            ],
            [
                InlineKeyboardButton(text="📝 ملاحظة", callback_data=f"admin_note_{order_id}"),
                InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu"),
            ],
        ]
    )
