"""Concise first-run terms shown before customer registration is accepted."""


ONBOARDING_TERMS = {
    "ar": """━━━ <b>الشروط الأساسية لاستخدام المنارة</b> ━━━

قبل المتابعة، يرجى معرفة النقاط الأساسية التالية:

<b>1. طبيعة الخدمة</b>
المنارة واجهة تقنية لإدارة طلبات شراء USDT والدفع عبر وسائل ShamCash المعتمدة. لا نحتفظ بالأصول الرقمية ولا نطلب منك تحويل الأموال خارج مسار الطلب الرسمي داخل البوت.

<b>2. مسؤولية بيانات الطلب</b>
أنت مسؤول عن صحة عنوان محفظة USDT والشبكة المختارة وأي بيانات تقدمها قبل تنفيذ الطلب.

<b>3. الدفع والطلب</b>
الدفع يتم فقط عبر وسيلة الدفع التي يعرضها البوت للطلب. يتم تثبيت بيانات الطلب الأساسية، بما فيها المبلغ وسعر الصرف وبيانات وسيلة الدفع، عند إنشاء الطلب.

<b>4. التوثيق والخصوصية</b>
قد نجمع بيانات التوثيق اللازمة للتحقق من الحساب وحمايته وتنفيذ الطلبات، مثل رقم الهاتف والاسم وبيانات حساب ShamCash والعناوين وQR المرتبط بها. لا نستخدم هذه البيانات للتسويق ولا نبيعها أو نشاركها تجارياً مع أطراف ثالثة.

<b>5. الأمان ومكافحة الاحتيال</b>
لن نطلب منك تجاوز مسار الدفع الرسمي أو تحويل الأموال إلى عنوان خارجي عبر رسالة خاصة. عند وجود طلب مشبوه، أوقف العملية وتواصل مع الدعم الرسمي.

<b>6. السجلات والتحديثات</b>
قد نحتفظ بالسجلات التي يلزم الاحتفاظ بها لأسباب أمنية أو محاسبية أو قانونية، حتى عند طلب حذف الحساب. وقد نحدّث الشروط عند الحاجة الأمنية أو التشغيلية أو القانونية.

━━━━━━━━━━━━━━━━━━━━
<b>يمكنك بعد التسجيل فتح «الشروط والسياسات» في أي وقت لقراءة السياسة الكاملة بالتفصيل حسب الأقسام.</b>

<b>بالضغط على «أوافق» فإنك تقر بأنك قرأت هذه الشروط الأساسية وتوافق على استخدامها للخدمة.</b>""",
    "en": """━━━ <b>Al-Manara Essential Terms</b> ━━━

Before continuing, please review these essential points:

<b>1. Service Nature</b>
Al-Manara is a technical interface for managing USDT purchase orders and payments through approved ShamCash methods. We do not custody digital assets and will not ask you to transfer funds outside the official bot flow.

<b>2. Order Data Responsibility</b>
You are responsible for the accuracy of your USDT wallet address, selected network, and other information you provide before execution.

<b>3. Payments & Orders</b>
Payments are made only through the payment method shown by the bot for the order. Core order data, including amount, exchange rate, and payment-method data, is fixed when the order is created.

<b>4. Verification & Privacy</b>
We may collect verification data required to protect the account and process orders, such as phone number, name, ShamCash account data, addresses, and associated QR data. This data is not used for marketing, sold, or commercially shared with third parties.

<b>5. Security & Anti-Fraud</b>
We will not ask you to bypass the official payment flow or transfer funds to an external address through a private message. If a request appears suspicious, stop and contact official support.

<b>6. Records & Updates</b>
We may retain records when required for security, accounting, or legal reasons, including after an account-deletion request. Terms may be updated when required for security, operations, or legal compliance.

━━━━━━━━━━━━━━━━━━━━
<b>After registration, you can open “Terms & Policies” at any time to read the complete policy by section.</b>

<b>By clicking “Agree”, you acknowledge that you have read these essential terms and agree to use the service under them.</b>""",
}


def get_onboarding_terms(lang: str) -> str:
    """Return concise first-run terms without replacing the full legal policy."""
    return ONBOARDING_TERMS.get(lang, ONBOARDING_TERMS["ar"])
