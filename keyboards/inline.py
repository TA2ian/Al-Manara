"""Inline keyboards for the bot."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def terms_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Terms acceptance keyboard."""
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ أوافق على الشروط", callback_data="accept_terms"),
                InlineKeyboardButton(text="❌ لا أوافق", callback_data="decline_terms")
            ]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ I Agree", callback_data="accept_terms"),
                InlineKeyboardButton(text="❌ I Decline", callback_data="decline_terms")
            ]
        ])


def main_menu_inline(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Main menu inline keyboard."""
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 حسابي", callback_data="menu_profile"),
                InlineKeyboardButton(text="💱 السعر", callback_data="menu_rate"),
                InlineKeyboardButton(text="✉️ اقتراح", callback_data="menu_feedback")
            ],
            [
                InlineKeyboardButton(text="🆘 دعم", callback_data="menu_support"),
                InlineKeyboardButton(text="📖 مساعدة", callback_data="menu_help")
            ]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Profile", callback_data="menu_profile"),
                InlineKeyboardButton(text="💱 Rate", callback_data="menu_rate"),
                InlineKeyboardButton(text="✉️ Feedback", callback_data="menu_feedback")
            ],
            [
                InlineKeyboardButton(text="🆘 Support", callback_data="menu_support"),
                InlineKeyboardButton(text="📖 Help", callback_data="menu_help")
            ]
        ])


def network_selection_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Network selection keyboard."""
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="BEP20 (BNB Chain)", callback_data="network_BEP20"),
                InlineKeyboardButton(text="TRC20 (TRON)", callback_data="network_TRC20")
            ],
            [
                InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_order")
            ]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="BEP20 (BNB Chain)", callback_data="network_BEP20"),
                InlineKeyboardButton(text="TRC20 (TRON)", callback_data="network_TRC20")
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order")
            ]
        ])


def currency_selection_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Currency selection keyboard."""
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇸 الدولار الأمريكي (USD)", callback_data="currency_USD"),
                InlineKeyboardButton(text="🇸🇾 الليرة السورية (SYP)", callback_data="currency_SYP")
            ],
            [
                InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_wallet")
            ]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇸 US Dollar (USD)", callback_data="currency_USD"),
                InlineKeyboardButton(text="🇸🇾 Syrian Pound (SYP)", callback_data="currency_SYP")
            ],
            [
                InlineKeyboardButton(text="🔙 Back", callback_data="back_to_wallet")
            ]
        ])


def order_confirmation_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Order confirmation keyboard."""
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأكيد وإرسال", callback_data="confirm_order"),
                InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_order")
            ]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm & Submit", callback_data="confirm_order"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order")
            ]
        ])


def rating_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Customer rating keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐", callback_data="rate_1"),
            InlineKeyboardButton(text="⭐⭐", callback_data="rate_2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data="rate_3"),
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rate_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rate_5")
        ]
    ])


def cancel_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Cancel keyboard."""
    text = "❌ إلغاء" if lang == 'ar' else "❌ Cancel"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="cancel")]
    ])


def back_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Back keyboard."""
    text = "🔙 رجوع" if lang == 'ar' else "🔙 Back"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="back")]
    ])


def receipt_upload_keyboard(order_id: int, lang: str = 'ar') -> InlineKeyboardMarkup:
    """Upload receipt keyboard for user."""
    text = "📎 رفع إيصال الدفع" if lang == 'ar' else "📎 Upload Receipt"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"upload_receipt_{order_id}")]
    ])


def skip_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Skip QR upload keyboard."""
    text = "⏭️ تخطي" if lang == 'ar' else "⏭️ Skip"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="skip_qr")]
    ])


def start_verification_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Start verification process keyboard."""
    text = "🔒 بدء التوثيق" if lang == 'ar' else "🔒 Start Verification"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="start_verification")]
    ])


def admin_verify_keyboard(user_telegram_id: int, full_name: str, shamcash_account: str) -> InlineKeyboardMarkup:
    """Admin verification action keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ توثيق", callback_data=f"verify_approve_{user_telegram_id}"),
            InlineKeyboardButton(text="❌ رفض", callback_data=f"verify_reject_{user_telegram_id}")
        ]
    ])


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin menu keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 الطلبات المعلقة", callback_data="admin_pending_orders"),
            InlineKeyboardButton(text="📋 جميع النشطة", callback_data="admin_active_orders")
        ],
        [
            InlineKeyboardButton(text="📊 لوحة التحكم", callback_data="admin_dashboard"),
            InlineKeyboardButton(text="💱 تحديث السعر", callback_data="admin_update_rate")
        ],
        [
            InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="admin_settings"),
            InlineKeyboardButton(text="📨 إشعار جماعي", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🔍 بحث عن عميل", callback_data="admin_search_user"),
            InlineKeyboardButton(text="🔍 بحث عن طلب", callback_data="admin_search_order")
        ],
        [
            InlineKeyboardButton(text="📈 التحليلات", callback_data="admin_analytics"),
            InlineKeyboardButton(text="📝 Logs", callback_data="admin_logs")
        ],
        [
            InlineKeyboardButton(text="📋 النسخ الاحتياطية", callback_data="admin_backups")
        ]
    ])


def order_admin_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    """Order actions for admin."""
    buttons = []

    if status == 'pending':
        buttons.append([
            InlineKeyboardButton(text="✅ موافقة", callback_data=f"admin_approve_{order_id}"),
            InlineKeyboardButton(text="❌ رفض", callback_data=f"admin_reject_{order_id}")
        ])
    elif status == 'waiting_payment':
        buttons.append([
            InlineKeyboardButton(text="✅ تأكيد الدفع", callback_data=f"admin_confirm_payment_{order_id}"),
            InlineKeyboardButton(text="❌ رفض الإيصال", callback_data=f"admin_reject_receipt_{order_id}")
        ])
    elif status == 'payment_confirmed':
        buttons.append([
            InlineKeyboardButton(text="🚀 إرسال USDT", callback_data=f"admin_send_usdt_{order_id}")
        ])

    buttons.append([
        InlineKeyboardButton(text="📝 ملاحظة", callback_data=f"admin_note_{order_id}"),
        InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_pending_orders")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_keyboard() -> InlineKeyboardMarkup:
    """Settings keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💱 سعر الصرف", callback_data="setting_rate"),
            InlineKeyboardButton(text="💰 الرسوم", callback_data="setting_fees")
        ],
        [
            InlineKeyboardButton(text="📱 شام كاش USD", callback_data="setting_shamcash_usd"),
            InlineKeyboardButton(text="📱 شام كاش SYP", callback_data="setting_shamcash_syp")
        ],
        [
            InlineKeyboardButton(text="⏱ مهلة الدفع", callback_data="setting_timeout"),
            InlineKeyboardButton(text="📊 الحدود", callback_data="setting_limits")
        ],
        [
            InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_menu")
        ]
    ])


def quick_actions_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Quick actions for returning users."""
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 إعادة الطلب السابق", callback_data="quick_reorder"),
                InlineKeyboardButton(text="📋 نسخ عنواني", callback_data="quick_wallet")
            ],
            [
                InlineKeyboardButton(text="💱 السعر الحالي", callback_data="quick_rate"),
                InlineKeyboardButton(text="📞 التواصل", callback_data="quick_contact")
            ]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Reorder", callback_data="quick_reorder"),
                InlineKeyboardButton(text="📋 Copy Wallet", callback_data="quick_wallet")
            ],
            [
                InlineKeyboardButton(text="💱 Current Rate", callback_data="quick_rate"),
                InlineKeyboardButton(text="📞 Contact", callback_data="quick_contact")
            ]
        ])
