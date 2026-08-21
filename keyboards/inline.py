"""Inline keyboards for the bot."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def terms_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ أوافق على الشروط", callback_data="accept_terms"), InlineKeyboardButton(text="❌ لا أوافق", callback_data="decline_terms")]])
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ I Agree", callback_data="accept_terms"), InlineKeyboardButton(text="❌ I Decline", callback_data="decline_terms")]])


def main_menu_inline(lang: str = 'ar') -> InlineKeyboardMarkup:
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 حسابي", callback_data="menu_profile"), InlineKeyboardButton(text="👛 محافظي", callback_data="menu_wallets")],
            [InlineKeyboardButton(text="💱 سعر الصرف", callback_data="menu_rate"), InlineKeyboardButton(text="📖 مساعدة", callback_data="menu_help")],
            [InlineKeyboardButton(text="📋 إخلاء المسؤولية", callback_data="menu_disclaimer")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Profile", callback_data="menu_profile"), InlineKeyboardButton(text="👛 My Wallets", callback_data="menu_wallets")],
        [InlineKeyboardButton(text="💱 Exchange Rate", callback_data="menu_rate"), InlineKeyboardButton(text="📖 Help", callback_data="menu_help")],
        [InlineKeyboardButton(text="📋 Disclaimer", callback_data="menu_disclaimer")]
    ])


def network_selection_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    label = "❌ إلغاء" if lang == 'ar' else "❌ Cancel"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BEP20 (BNB Chain)", callback_data="network_BEP20"), InlineKeyboardButton(text="TRC20 (TRON)", callback_data="network_TRC20")], [InlineKeyboardButton(text=label, callback_data="cancel_order")]])


def currency_selection_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇺🇸 الدولار الأمريكي (USD)", callback_data="currency_USD"), InlineKeyboardButton(text="🇸🇾 الليرة السورية الجديدة (NEW.SYP)", callback_data="currency_NEW.SYP")], [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_wallet")]])
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇺🇸 US Dollar (USD)", callback_data="currency_USD"), InlineKeyboardButton(text="🇸🇾 Syrian Pound (NEW.SYP)", callback_data="currency_NEW.SYP")], [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_wallet")]])


def order_confirmation_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    if lang == 'ar':
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ تأكيد وإرسال", callback_data="confirm_order"), InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_order")]])
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Confirm & Submit", callback_data="confirm_order"), InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order")]])


def rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"⭐ {i} - {['سيء جداً','سيء','مقبول','جيد','ممتاز'][i-1]}", callback_data=f"rate_{i}_{order_id}")] for i in range(1,6)])


def cancel_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء" if lang == 'ar' else "❌ Cancel", callback_data="cancel")]])


def back_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع" if lang == 'ar' else "🔙 Back", callback_data="back")]])


def receipt_upload_keyboard(order_id: int, lang: str = 'ar') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📎 رفع إيصال الدفع" if lang == 'ar' else "📎 Upload Receipt", callback_data=f"upload_receipt_{order_id}")]])


def skip_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ تخطي" if lang == 'ar' else "⏭️ Skip", callback_data="skip_qr")]])


def start_verification_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔒 بدء التوثيق" if lang == 'ar' else "🔒 Start Verification", callback_data="start_verification")]])


def admin_verify_keyboard(user_telegram_id: int, full_name: str, shamcash_account: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ توثيق", callback_data=f"verify_approve_{user_telegram_id}"), InlineKeyboardButton(text="❌ رفض", callback_data=f"verify_reject_{user_telegram_id}")], [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")]])


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 المعلقة", callback_data="admin_pending_orders"), InlineKeyboardButton(text="📋 جميع النشطة", callback_data="admin_active_orders"), InlineKeyboardButton(text="🔍 تفاصيل طلب", callback_data="admin_search_order")],
        [InlineKeyboardButton(text="📊 الإحصائيات", callback_data="admin_dashboard"), InlineKeyboardButton(text="📈 التحليلات", callback_data="admin_analytics"), InlineKeyboardButton(text="📍 العملاء", callback_data="admin_list_users")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="admin_settings"), InlineKeyboardButton(text="💱 السعر", callback_data="admin_update_rate"), InlineKeyboardButton(text="📨 إشعار", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔍 بحث عميل", callback_data="admin_search_user"), InlineKeyboardButton(text="📝 السجلات", callback_data="admin_logs"), InlineKeyboardButton(text="📋 نسخ احتياطي", callback_data="admin_backups")],
        [InlineKeyboardButton(text="⭐ توثيق تلقائي", callback_data="admin_auto_approve"), InlineKeyboardButton(text="🛑 صيانة", callback_data="admin_maintenance")]
    ])


def order_admin_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    buttons=[]
    if status == 'pending': buttons.append([InlineKeyboardButton(text="✅ موافقة", callback_data=f"admin_approve_{order_id}"), InlineKeyboardButton(text="❌ رفض", callback_data=f"admin_reject_{order_id}")])
    elif status == 'waiting_payment': buttons.append([InlineKeyboardButton(text="💳 في انتظار الدفع", callback_data=f"admin_noop_{order_id}")])
    elif status == 'receipt_received': buttons.append([InlineKeyboardButton(text="✅ تأكيد الدفع", callback_data=f"admin_confirm_payment_{order_id}"), InlineKeyboardButton(text="❌ رفض الإيصال", callback_data=f"admin_reject_receipt_{order_id}")])
    elif status == 'payment_confirmed': buttons.append([InlineKeyboardButton(text="🚀 إرسال USDT", callback_data=f"admin_send_usdt_{order_id}")])
    buttons.append([InlineKeyboardButton(text="📝 ملاحظة", callback_data=f"admin_note_{order_id}"), InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_detail_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 سجل الحالة", callback_data=f"admin_timeline_{order_id}"), InlineKeyboardButton(text="📝 ملاحظة", callback_data=f"admin_note_{order_id}")], [InlineKeyboardButton(text="🔙 رجوع للقائمة", callback_data="admin_menu")]])


def order_pagination_keyboard(page: int, total_pages: int, list_type: str) -> InlineKeyboardMarkup:
    buttons=[]
    if total_pages>1:
        nav=[]
        if page>0: nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{list_type}_page_{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="admin_noop"))
        if page<total_pages-1: nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{list_type}_page_{page+1}"))
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def auto_approve_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{'⏸' if enabled else '▶️'} {'إيقاف' if enabled else 'تفعيل'} التوثيق التلقائي", callback_data="admin_auto_approve_toggle")], [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_menu")]])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💱 سعر الصرف", callback_data="setting_rate"), InlineKeyboardButton(text="💰 الرسوم", callback_data="setting_fees")], [InlineKeyboardButton(text="📱 شام كاش USD", callback_data="setting_shamcash_usd"), InlineKeyboardButton(text="📱 شام كاش NEW.SYP", callback_data="setting_shamcash_new_syp")], [InlineKeyboardButton(text="👤 اسم شام كاش", callback_data="setting_shamcash_name"), InlineKeyboardButton(text="⏱ مهلة الدفع", callback_data="setting_timeout")], [InlineKeyboardButton(text="📊 الحدود", callback_data="setting_limits"), InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_menu")]])


def preset_amounts_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    amounts=[50,100,200,500,1000]; rows=[]
    for i in range(0,len(amounts),2): rows.append([InlineKeyboardButton(text=f"{a} USDT", callback_data=f"amount_preset_{a}") for a in amounts[i:i+2]])
    rows.append([InlineKeyboardButton(text="✏️ مبلغ آخر" if lang == 'ar' else "✏️ Other Amount", callback_data="amount_custom")])
    rows.append([InlineKeyboardButton(text="❌ " + ("إلغاء" if lang == 'ar' else "Cancel"), callback_data="cancel_order")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_select_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇸🇦 العربية\u200F", callback_data="lang_ar"), InlineKeyboardButton(text="🇬🇧 English\u200E", callback_data="lang_en")]])


def saved_addresses_keyboard(addresses: list, lang: str = 'ar', select_mode: bool = False) -> InlineKeyboardMarkup:
    buttons=[]
    for addr in addresses:
        label=addr.get('label','') or ''; full=addr['address']; short_addr=full[:6]+"..."+full[-4:]; display=f"{label} - {short_addr}" if label else short_addr; prefix="select_addr_" if select_mode else "view_addr_"
        buttons.append([InlineKeyboardButton(text=f"📍 {display} [{addr['network']}]", callback_data=f"{prefix}{addr['id']}")])
    buttons.append([InlineKeyboardButton(text="❌ " + ("إلغاء" if lang == 'ar' else "Cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def orders_pagination_keyboard(current_page: int, total_pages: int, lang: str = 'ar') -> InlineKeyboardMarkup:
    buttons=[]; nav=[]
    if current_page>1: nav.append(InlineKeyboardButton(text="⬅️ السابق" if lang == 'ar' else "⬅️ Previous", callback_data=f"orders_page_{current_page-1}"))
    if current_page<total_pages: nav.append(InlineKeyboardButton(text="التالي ➡️" if lang == 'ar' else "Next ➡️", callback_data=f"orders_page_{current_page+1}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="❌ " + ("إغلاق" if lang == 'ar' else "Close"), callback_data="close_orders_list")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def quick_actions_keyboard(lang: str = 'ar') -> InlineKeyboardMarkup:
    if lang == 'ar':
        buttons=[[InlineKeyboardButton(text="🔄 إعادة الطلب السابق", callback_data="quick_reorder"), InlineKeyboardButton(text="📍 عناويني المحفوظة", callback_data="quick_saved_addresses")], [InlineKeyboardButton(text="💱 سعر الصرف", callback_data="quick_rate"), InlineKeyboardButton(text="📞 دعم واقتراح", callback_data="quick_contact")], [InlineKeyboardButton(text="📋 إخلاء المسؤولية", callback_data="menu_disclaimer"), InlineKeyboardButton(text="🌐 تغيير اللغة", callback_data="quick_change_lang")]]
    else:
        buttons=[[InlineKeyboardButton(text="🔄 Reorder", callback_data="quick_reorder"), InlineKeyboardButton(text="📍 Saved Addresses", callback_data="quick_saved_addresses")], [InlineKeyboardButton(text="💱 Exchange Rate", callback_data="quick_rate"), InlineKeyboardButton(text="📞 Support & Feedback", callback_data="quick_contact")], [InlineKeyboardButton(text="📋 Disclaimer", callback_data="menu_disclaimer"), InlineKeyboardButton(text="🌐 Change Language", callback_data="quick_change_lang")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
