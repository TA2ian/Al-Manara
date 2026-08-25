# خريطة لوحات المفاتيح — Keyboard Map

هذه الوثيقة تصف **السطح الحالي** للـTelegram bot كما هو في `keyboards/` و`handlers/`. لا تُستخدم كـruntime configuration.

## العميل — Customer

### Reply Keyboard

| الزر | الوظيفة |
|---|---|
| `💰 إنشاء طلب شراء` / `💰 Buy Order` | بدء إنشاء طلب |
| `📋 طلباتي` / `📋 Orders` | عرض الطلبات السابقة |
| `⚙️ القائمة` / `⚙️ Menu` | فتح الإجراءات السريعة |

### Main Inline Menu

| الزر | Callback | الوظيفة |
|---|---|---|
| `👤 حسابي` / `👤 Profile` | `menu_profile` | الملف الشخصي |
| `👛 محافظي` / `👛 My Wallets` | `menu_wallets` | المحافظ المحفوظة |
| `💱 سعر الصرف` / `💱 Exchange Rate` | `menu_rate` | سعر الصرف |
| `📖 مساعدة` / `📖 Help` | `menu_help` | المساعدة |
| `📋 إخلاء المسؤولية` / `📋 Disclaimer` | `menu_disclaimer` | إخلاء المسؤولية |

### Quick Actions

| الزر | Callback | الوظيفة |
|---|---|---|
| `🔄 إعادة الطلب السابق` / `🔄 Reorder` | `quick_reorder` | إعادة آخر طلب |
| `📍 عناويني المحفوظة` / `📍 Saved Addresses` | `quick_saved_addresses` | المحافظ/العناوين المحفوظة |
| `💱 سعر الصرف` / `💱 Exchange Rate` | `quick_rate` | سعر الصرف |
| `📞 دعم واقتراح` / `📞 Support & Feedback` | `quick_contact` | الدعم والاقتراحات |
| `📋 إخلاء المسؤولية` / `📋 Disclaimer` | `menu_disclaimer` | إخلاء المسؤولية |
| `🌐 تغيير اللغة` / `🌐 Change Language` | `quick_change_lang` | تغيير اللغة |

### Order Flow

1. اختيار اللغة: `🇸🇦 العربية` / `🇬🇧 English`
2. الموافقة على الشروط: `✅ أوافق على الشروط` / `❌ لا أوافق`
3. اختيار الشبكة: `BEP20 (BNB Chain)` / `TRC20 (TRON)` + إلغاء
4. اختيار العملة: `USD` / `NEW.SYP` + رجوع
5. اختيار المبلغ: presets أو مبلغ مخصص
6. تأكيد الطلب: `confirm_order` / إلغاء
7. بعد الدفع: `📎 رفع إيصال الدفع`
8. التقييم: من 1 إلى 5 نجوم

> إعداد وسائل الدفع الخاصة بـShamCash ليس جزءاً من تدفق العميل؛ يتم من لوحة الإدارة عبر معالج مستقل.

### Wallet Flow

- يمكن إدخال العنوان ثم إرفاق QR مطابق.
- يمكن البدء بصورة QR، ثم استخراج العنوان والتحقق منه.
- أي عنوان في caption يجب أن يطابق العنوان المستخرج من QR.
- يتم رفض الصور غير الصالحة أو غير الآمنة قبل QR decoding.

## الأدمن — Admin

### Main Admin Menu

| الزر | Callback | الوظيفة |
|---|---|---|
| `📦 المعلقة` | `admin_pending_orders` | الطلبات المعلقة |
| `📋 جميع النشطة` | `admin_active_orders` | الطلبات النشطة |
| `🔍 تفاصيل طلب` | `admin_search_order` | البحث عن طلب |
| `📊 الإحصائيات` | `admin_dashboard` | لوحة الإحصائيات |
| `📈 التحليلات` | `admin_analytics` | التحليلات |
| `📍 العملاء` | `admin_list_users` | قائمة العملاء |
| `⚙️ الإعدادات` | `admin_settings` | الإعدادات التشغيلية |
| `💱 السعر` | `admin_update_rate` | تحديث سعر الصرف |
| `📨 إشعار` | `admin_broadcast` | الإشعارات الجماعية |
| `🔍 بحث عميل` | `admin_search_user` | البحث عن عميل |
| `📝 السجلات` | `admin_logs` | سجلات العمليات |
| `📋 نسخ احتياطي` | `admin_backups` | النسخ الاحتياطية |
| `⭐ توثيق تلقائي` | `admin_auto_approve` | إعداد التوثيق التلقائي |
| `🛑 صيانة` | `admin_maintenance` | وضع الصيانة |

### Order Actions

| الحالة | الإجراءات |
|---|---|
| `pending` | موافقة / رفض |
| `waiting_payment` | عرض حالة الدفع / رفض الطلب |
| `receipt_received` | تأكيد الدفع / رفض الإيصال / رفض الطلب |
| `payment_confirmed` | إرسال USDT / رفض الطلب |
| جميع الحالات ذات التفاصيل | ملاحظة / العودة للوحة التحكم |

### ShamCash Payment Method Setup

يوجد **مالك واحد canonical** لإعداد وسائل الدفع: `handlers/payment_method_setup_policy.py`.

المعالج المتتابع هو:

1. اختيار وسيلة الدفع/العملة.
2. **اسم المستلم**.
3. **عنوان الاستلام**.
4. **QR**.
5. استخراج العنوان من QR ومقارنته بالعنوان المدخل.
6. مراجعة البيانات.
7. حفظها بعد تأكيد صريح.

الوسائل الحالية:

- `shamcash_usd` → `USD`
- `shamcash_new_syp` → `NEW.SYP`

### Operational Settings

| الزر | Callback |
|---|---|
| `💰 الرسوم` | `setting_fees` |
| `⏱ مهلة الدفع` | `setting_timeout` |
| `📊 الحدود` | `setting_limits` |
| `🔙 رجوع` | `admin_menu` |

> بيانات حسابات الدفع وQR لها owner مستقل في `payment_method_setup_policy.py` ولا تُدار من `settings_keyboard()`.

## Security Notes

- Media validation تتم عبر `services.media_security` قبل QR/OCR/PDF parsing.
- الحد المركزي الحالي للرفع: **2 MB**.
- الصور المسموحة: JPEG / PNG / WebP.
- PDF المسموح للإيصالات: **صفحة واحدة فقط**.
- يتم التحقق من MIME، extension، بنية الملف، الأبعاد، وعدد الـpixels قبل المعالجة الثقيلة.

## Canonical Routing

الـlegacy facades التالية غير مطلوبة في الـproduction surface:

- `handlers.admin`
- `handlers.order`
- `handlers.my_orders`
- `handlers.verification`
- `handlers.legacy_wallet_guard`
- `handlers.verification_pending_guard`
- `services.order_wallet_guard`
- `database_wallet_guards`
- `handlers.payment_methods`
- `handlers.receipt_transition_policy`

الـRelease Gate يختبر وجود الـcanonical policy modules وغياب هذه الطبقات القديمة. 
