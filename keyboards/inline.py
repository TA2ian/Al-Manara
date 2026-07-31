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
                InlineKeyboardButton(text="💱 سعر الصرف", callback_data="menu_rate"),
                InlineKeyboardButton(text="📖 مساعدة", callback_data="menu_help")
            ],
            [
                InlineKeyboardButton(text="📋 إخلاء المسؤولية", callback_data="menu_disclaimer")
            ]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Profile", callback_data="menu_profile"),
                InlineKeyboardButton(text="💱 Exchange Rate", callback_data="menu_rate"),
                InlineKeyboardButton(text="📖 Help", callback_data="menu_help")
            ],
            [
                InlineKeyboardButton(text="📋 Disclaimer", callback_data="menu_disclaimer")
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


def rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Customer rating keyboard with order id - each row has one clear rating option."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 1 - سيء جداً", callback_data=f"rate_1_{order_id}")],
        [InlineKeyboardButton(text="⭐⭐ 2 - سيء", callback_data=f"rate_2_{order_id}")],
        [InlineKeyboardButton(text="⭐⭐⭐ 3 - مقبول", callback_data=f"rate_3_{order_id}")],
        [InlineKeyboardButton(text="⭐⭐⭐⭐ 4 - جيد", callback_data=f"rate_4_{order_id}")],
        [InlineKeyboardButton(text="⭐⭐⭐⭐⭐ 5 - ممتاز", callback_data=f"rate_5_{order_id}")]
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
            InlineKeyboardButton(text="📦 المعلقة", callback_data="admin_pending_orders"),
            InlineKeyboardButton(text="📋 جميع النشطة", callback_data="admin_active_orders"),
            InlineKeyboardButton(text="🔍 تفاصيل طلب", callback_data="admin_search_order")
        ],
        [
            InlineKeyboardButton(text="📊 الإحصائيات", callback_data="admin_dashboard"),
            InlineKeyboardButton(text="📈 التحليلات", callback_data="admin_analytics"),
            InlineKeyboardButton(text="📍 العملاء", callback_data="admin_list_users")
        ],
        [
            InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="admin_settings"),
            InlineKeyboardButton(text="💱 السعر", callback_data="admin_update_rate"),
            InlineKeyboardButton(text="📨 إشعار", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🔍 بحث عميل", callback_data="admin_search_user"),
            InlineKeyboardButton(text="📝 السجلات", callback_data="admin_logs"),
            InlineKeyboardButton(text="📋 نسخ احتياطي", callback_data="admin_backups")
        ],
        [
            InlineKeyboardButton(text="⭐ توثيق تلقائي", callback_data="admin_auto_approve"),
            InlineKeyboardButton(text="🛑 صيانة", callback_data="admin_maintenance")
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
            InlineKeyboardButton(text="💳 في انتظار الدفع", callback_data=f"admin_noop_{order_id}")
        ])
    elif status == 'receipt_received':
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
        InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_detail_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Full detail view keyboard for an order."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 سجل الحالة", callback_data=f"admin_timeline_{order_id}"),
            InlineKeyboardButton(text="📝 ملاحظة", callback_data=f"admin_note_{order_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 رجوع للقائمة", callback_data="admin_menu")
        ]
    ])


def order_pagination_keyboard(page: int, total_pages: int, list_type: str) -> InlineKeyboardMarkup:
    """Pagination for order lists."""
    buttons = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{list_type}_page_{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="admin_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{list_type}_page_{page+1}"))
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def auto_approve_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    """Auto-approve settings keyboard."""
    toggle_text = "✅ مفعل" if enabled else "❌ معطل"
    toggle_data = "admin_auto_approve_toggle"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'⏸' if enabled else '▶️'} {'إيقاف' if enabled else 'تفعيل'} التوثيق التلقائي", callback_data=toggle_data)],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_menu")]
    ])


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
            InlineKeyboardButton(text="👤 اسم شام كاش", callback_data="setting_shamcash_name"),
            InlineKeyboardButton(text="⏱ مهلة الدفع", callback_data="setting_timeout")
        ],
        [
            InlineKeyboardButton(text="📊 الحدود", callback_data="setting_limits"),
            InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_menu")
        ]
    ])


def preset_amounts_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Preset USDT amount selection keyboard."""
    # Common preset amounts - adjust as needed
    amounts = [50, 100, 200, 500, 1000]
    rows = []
    # Two per row
    for i in range(0, len(amounts), 2):
        row = []
        for amt in amounts[i:i+2]:
            row.append(InlineKeyboardButton(text=f"{amt} USDT", callback_data=f"amount_preset_{amt}"))
        rows.append(row)
    # Custom amount at the bottom
    custom_text = "✏️ مبلغ آخر" if lang == 'ar' else "✏️ Other Amount"
    rows.append([InlineKeyboardButton(text=custom_text, callback_data="amount_custom")])
    rows.append([
        InlineKeyboardButton(text="❌ " + ("إلغاء" if lang == 'ar' else "Cancel"), callback_data="cancel_order")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_select_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard at start.
    Uses Unicode direction marks for proper RTL/LTR display:
    Arabic gets RLM (right-to-left) suffix, English gets LRM (left-to-right) suffix.
    """
    # \u200F = Right-to-Left Mark (RLM), \u200E = Left-to-Right Mark (LRM)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇸🇦 العربية\u200F", callback_data="lang_ar"),
            InlineKeyboardButton(text="🇬🇧 English\u200E", callback_data="lang_en")
        ]
    ])


def saved_addresses_keyboard(addresses: list, lang: str = 'ar', select_mode: bool = False) -> InlineKeyboardMarkup:
    """Display saved addresses. If select_mode, allow choosing one for order."""
    buttons = []
    for addr in addresses:
        label = addr.get('label', '') or ''
        full = addr['address']
        short_addr = full[:6] + "..." + full[-4:]
        display = f"{label} - {short_addr}" if label else short_addr
        prefix = "select_addr_" if select_mode else "view_addr_"
        buttons.append([
            InlineKeyboardButton(text=f"📍 {display} [{addr['network']}]", callback_data=f"{prefix}{addr['id']}")
        ])
    buttons.append([
        InlineKeyboardButton(text="❌ " + ("إلغاء" if lang == 'ar' else "Cancel"), callback_data="cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def orders_pagination_keyboard(current_page: int, total_pages: int, lang: str = 'ar') -> InlineKeyboardMarkup:
    """Pagination keyboard for orders list."""
    buttons = []
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ السابق" if lang == 'ar' else "⬅️ Previous",
            callback_data=f"orders_page_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="التالي ➡️" if lang == 'ar' else "Next ➡️",
            callback_data=f"orders_page_{current_page + 1}"
        ))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([
        InlineKeyboardButton(
            text="❌ " + ("إغلاق" if lang == 'ar' else "Close"),
            callback_data="close_orders_list"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def quick_actions_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    """Quick actions for returning users."""
    if lang == 'ar':
        buttons = [
            [
                InlineKeyboardButton(text="🔄 إعادة الطلب السابق", callback_data="quick_reorder"),
                InlineKeyboardButton(text="📍 عناويني المحفوظة", callback_data="quick_saved_addresses")
            ],
            [
                InlineKeyboardButton(text="💱 سعر الصرف", callback_data="quick_rate"),
                InlineKeyboardButton(text="📞 دعم واقتراح", callback_data="quick_contact")
            ],
            [
                InlineKeyboardButton(text="📋 إخلاء المسؤولية", callback_data="menu_disclaimer"),
                InlineKeyboardButton(text="🌐 تغيير اللغة", callback_data="quick_change_lang")
            ]
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton(text="🔄 Reorder", callback_data="quick_reorder"),
                InlineKeyboardButton(text="📍 Saved Addresses", callback_data="quick_saved_addresses")
            ],
            [
                InlineKeyboardButton(text="💱 Exchange Rate", callback_data="quick_rate"),
                InlineKeyboardButton(text="📞 Support & Feedback", callback_data="quick_contact")
            ],
            [
                InlineKeyboardButton(text="📋 Disclaimer", callback_data="menu_disclaimer"),
                InlineKeyboardButton(text="🌐 Change Language", callback_data="quick_change_lang")
            ]
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
