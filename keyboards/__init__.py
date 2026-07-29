"""Keyboards package."""
from .reply import compact_reply_keyboard
from .inline import (
    terms_keyboard,
    main_menu_inline,
    network_selection_keyboard,
    currency_selection_keyboard,
    order_confirmation_keyboard,
    rating_keyboard,
    cancel_keyboard,
    back_keyboard,
    admin_menu_keyboard,
    order_admin_keyboard,
    settings_keyboard
)

__all__ = [
    "compact_reply_keyboard",
    "terms_keyboard",
    "main_menu_inline",
    "network_selection_keyboard",
    "currency_selection_keyboard",
    "order_confirmation_keyboard",
    "rating_keyboard",
    "cancel_keyboard",
    "back_keyboard",
    "admin_menu_keyboard",
    "order_admin_keyboard",
    "settings_keyboard"
]
