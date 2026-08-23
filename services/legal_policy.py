"""Canonical customer-facing terms and privacy policy."""


TERMS_TEXT = {
    "ar": """━━━ <b>شروط الخدمة والخصوصية</b> ━━━

<b>1. طبيعة الخدمة</b>
يعمل البوت كواجهة تقنية لإدارة طلبات شراء USDT والدفع عبر ShamCash. البوت لا يحتفظ بالأصول الرقمية ولا يطلب منك تحويل الأموال خارج مسار الطلب الرسمي داخل البوت.

<b>2. مسؤولية بيانات الطلب</b>
- أنت مسؤول عن صحة بيانات الطلب، بما فيها عنوان محفظة USDT والشبكة المختارة.
- قبل تنفيذ الطلب، يجب التأكد من صحة العنوان ومطابقة الشبكة.
- بعد تثبيت الطلب، يتم الاحتفاظ بالـsnapshot المطلوب لتنفيذ ومراجعة المعاملة.

<b>3. بيانات التوثيق والخصوصية</b>
نجمع بيانات التوثيق اللازمة للتحقق من الحساب وحمايته، مثل رقم الهاتف المشارك من Telegram، الاسم الكامل، وبيانات حساب ShamCash وعنوان الاستلام وQR المرتبط به.

تُستخدم بيانات التوثيق حصراً لأغراض:
• التحقق من الحساب ومنع انتحال الهوية والاحتيال.
• حماية الحسابات والطلبات والتحقق من سلامة المعاملات.
• تنفيذ ومراجعة الطلبات المرتبطة بالحساب.
• الإجراءات القانونية اللازمة عند وجود احتيال أو إساءة استخدام أو طلب قانوني ملزم.

لا نستخدم بيانات التوثيق لأغراض تسويقية، ولا نبيعها أو نشاركها تجارياً مع أطراف ثالثة.

يتم الوصول إلى بيانات التوثيق وفق الصلاحيات اللازمة للعمل، وتُحفظ بطريقة آمنة، ويُسجل استخدامات المراجعة الإدارية الحساسة في سجلات التدقيق.

قد نحتفظ ببعض البيانات بالقدر اللازم للمتطلبات الأمنية أو المحاسبية أو القانونية، لذلك لا يعني طلب حذف الحساب حذف السجلات التي يجب الاحتفاظ بها بموجب القانون أو لمنع الاحتيال وحماية الحقوق.

<b>4. الدفع والمعاملات</b>
- الدفع يتم عبر وسائل ShamCash المعتمدة التي يعرضها البوت.
- سعر الصرف والمبالغ وبيانات وسيلة الدفع المطلوبة للطلب تُثبت ضمن الطلب عند إنشائه.
- قد تُرفض الطلبات التي لا تستوفي متطلبات التحقق أو الدفع أو الحماية من الاحتيال.

<b>5. الأمان ومكافحة الاحتيال</b>
لن نطلب منك عبر رسالة خاصة تحويل الأموال إلى عنوان خارجي أو تجاوز مسار الدفع الرسمي داخل البوت. إذا طلب منك أي شخص ذلك، فلا تنفذ الطلب وأبلغ الدعم عبر القنوات الرسمية.

<b>6. التحديثات</b>
قد يتم تحديث هذه الشروط عند الحاجة الأمنية أو التشغيلية أو القانونية. عند وجود تغيير جوهري، يتم عرضه للمستخدم قبل استمرار الاستخدام وفق ما يتطلبه النظام.

━━━━━━━━━━━━━━━━━━━━
<b>بالضغط على «أوافق» فإنك تقر بأنك قرأت وفهمت هذه الشروط وسياسة الخصوصية المرتبطة بها.</b>""",
    "en": """━━━ <b>Terms of Service & Privacy</b> ━━━

<b>1. Service Nature</b>
The bot is a technical interface for managing USDT purchase orders and ShamCash payments. It does not custody digital assets and will not ask you to transfer funds outside the official in-bot order flow.

<b>2. Order Data Responsibility</b>
- You are responsible for the accuracy of your order data, including the USDT wallet address and selected network.
- Verify the address and network before an order is executed.
- Once an order is fixed, the required snapshot is retained for execution and transaction review.

<b>3. Verification Data & Privacy</b>
We collect the verification data required to verify and protect your account, such as the phone number shared from Telegram, full name, and ShamCash receiving-account data including its address and associated QR.

Verification data is used only for:
• Account verification and protection against impersonation and fraud.
• Account and order security and transaction integrity checks.
• Processing and reviewing orders associated with the account.
• Necessary legal procedures in cases of fraud, abuse, or a binding legal request.

Verification data is not used for marketing, sold, or commercially shared with third parties.

Access to verification data is limited to what is required for operations, the data is stored securely, and sensitive administrative review actions are recorded in audit logs.

Some data may be retained when necessary for security, accounting, or legal requirements. Therefore, an account-deletion request does not require deletion of records that must be retained by law or to prevent fraud and protect rights.

<b>4. Payments & Transactions</b>
- Payments are made through the approved ShamCash methods shown by the bot.
- The exchange rate, amounts, and payment-method data required for an order are fixed in the order snapshot when it is created.
- Orders may be rejected when verification, payment, or anti-fraud requirements are not met.

<b>5. Security & Anti-Fraud</b>
We will not ask you through private messages to transfer funds to an external address or bypass the official bot payment flow. If anyone asks you to do so, do not proceed and report it through the official support channels.

<b>6. Updates</b>
These terms may be updated when required for security, operations, or legal compliance. Material changes will be presented to the user before continued use when required by the system.

━━━━━━━━━━━━━━━━━━━━
<b>By clicking “Agree”, you acknowledge that you have read and understood these terms and the associated privacy policy.</b>""",
}


def get_terms_text(lang: str, timeout: int) -> str:
    """Return the canonical terms/privacy text with runtime order timing."""
    text = TERMS_TEXT.get(lang, TERMS_TEXT["ar"])
    return text.replace("{timeout}", str(timeout))
