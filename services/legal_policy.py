"""Canonical customer-facing terms, privacy policy, and onboarding summary."""


START_TERMS_TEXT = {
    "ar": """━━━ <b>الشروط الأساسية لاستخدام Al-Manara</b> ━━━

<b>ما هي الخدمة؟</b>
Al-Manara واجهة تقنية لإدارة طلبات شراء USDT والدفع عبر وسائل ShamCash المعتمدة. لا يطلب البوت منك المفتاح الخاص أو عبارة الاسترداد أو كلمة مرور محفظتك، ولا يطلب تحويل الأموال خارج مسار الطلب الرسمي داخل البوت.

<b>الحماية وتقليل أخطاء الاستخدام</b>
صُممت الخدمة لتقليل أخطاء الاستخدام إلى أدنى مستوى عملي من خلال التحقق من بيانات الحساب، والمحفظة، والشبكة، وعنوان الاستلام، وQR المرتبط بالمحفظة، ثم إعادة مطابقة البيانات عند تثبيت الطلب. عندما تكون المحفظة مملوكة لك وآمنة وتقدم بيانات صحيحة، تساعد هذه الآليات على جعل أخطاء الإدخال أو اختيار الشبكة والعنوان قريبة جداً من الصفر، دون أن يعني ذلك ضماناً مطلقاً ضد فقدان الأصول أو اختراق الحساب.

<b>مسؤوليتك الأساسية</b>
أنت مسؤول عن امتلاك المحفظة وتأمين حسابك وبيانات الوصول إليها، وعن التأكد من أن عنوان الاستلام والشبكة والبيانات التي تعتمدها تخصك وصحيحة. لا ترسل seed phrase أو private key أو كلمات مرورك لأي شخص.

<b>الدفع</b>
لا ترسل أي مبلغ إلا وفق تعليمات الدفع الرسمية التي تظهر لك داخل مسار الطلب في البوت وبعد أن يصبح الطلب جاهزاً للدفع. لا تعتمد على تعليمات تصل عبر رسالة خاصة أو قناة غير رسمية.

<b>التوثيق والبيانات</b>
يتطلب استخدام الطلبات توثيق الحساب، وقد يشمل رقم الهاتف المرتبط بحساب Telegram، والاسم الكامل، وبيانات حساب ShamCash وQR. تستخدم هذه البيانات للتحقق والحماية وتنفيذ ومراجعة الطلبات ومكافحة الاحتيال والالتزامات القانونية عند الحاجة.

<b>الموافقة</b>
بالضغط على «أوافق» تقر بأنك قرأت وفهمت هذه الشروط الأساسية، وتوافق على استخدام الخدمة وفقها. يمكنك بعد التسجيل الوصول إلى الشروط والسياسات الكاملة والمفصلة من لوحة العميل في أي وقت.""",
    "en": """━━━ <b>Essential Al-Manara Terms</b> ━━━

<b>What is the service?</b>
Al-Manara is a technical interface for managing USDT purchase orders and payments through approved ShamCash methods. The bot will never ask for your private key, recovery phrase, or wallet password, and will not ask you to transfer funds outside the official in-bot order flow.

<b>Protection and error reduction</b>
The service is designed to reduce user errors as far as practical by validating account data, wallet, network, receiving address, and the wallet's linked QR, then rechecking the data when the order is fixed. When the wallet belongs to you, is secure, and the information you provide is correct, these controls can bring address and network input errors close to zero; this is not an absolute guarantee against asset loss or account compromise.

<b>Your primary responsibility</b>
You are responsible for owning and securing your wallet and its access credentials, and for confirming that the receiving address, network, and approved data are yours and correct. Never share a seed phrase, private key, or password with anyone.

<b>Payments</b>
Do not send any payment except according to the official payment instructions shown inside the bot's order flow after the order is ready for payment. Do not rely on instructions received through private messages or unofficial channels.

<b>Verification and data</b>
Using orders requires account verification, which may include the phone number linked to Telegram, full name, ShamCash receiving-account data, and QR. These data are used for verification, protection, order processing/review, anti-fraud measures, and necessary legal obligations.

<b>Consent</b>
By clicking “Agree”, you acknowledge that you have read and understood these essential terms and agree to use the service accordingly. After registration, you can access the complete detailed terms and policies from the customer panel at any time.""",
}


TERMS_TEXT = {
    "ar": """━━━ <b>الشروط والسياسات الكاملة</b> ━━━

<b>1. طبيعة الخدمة وآلية الحماية</b>
Al-Manara واجهة تقنية لإدارة طلبات شراء USDT والدفع عبر وسائل ShamCash المعتمدة. لا يحتفظ البوت بالأصول الرقمية، ولا يطلب المفتاح الخاص أو seed phrase أو كلمة مرور المحفظة، ولا يطلب تحويل الأموال خارج مسار الطلب الرسمي.

تعتمد الخدمة على عدة طبقات من التحقق قبل تثبيت الطلب، تشمل بيانات الحساب، ورقم الهاتف، والمحفظة المسجلة، والشبكة، وعنوان الاستلام، وQR المرتبط بالمحفظة، ثم إعادة مطابقة البيانات عند إنشاء الطلب. عندما تكون المحفظة مملوكة لك وآمنة وتقدم بيانات صحيحة، تساعد هذه الآليات على تقليل أخطاء الإدخال أو اختيار الشبكة والعنوان إلى مستوى قريب جداً من الصفر، دون ضمان مطلق ضد فقدان الأصول أو اختراق الحساب.

<b>2. المحفظة وعنوان الاستلام</b>
- يجب أن تكون المحفظة مملوكة لك وأن تحافظ على أمان حسابها وبيانات الوصول إليها.
- يتحمل المستخدم مسؤولية التأكد من صحة عنوان الاستلام والشبكة التي يريد استخدامها.
- يتم التحقق من العنوان والشبكة وQR المرتبط بالمحفظة قبل السماح باستخدامها في الطلب.
- يستخدم QR المحفوظ كوسيلة تحقق إضافية من هوية عنوان الاستلام.
- لا يمكن للنظام إثبات ملكية المحفظة من خلال العنوان وحده، لذلك تبقى مسؤولية الملكية وأمان الحساب على المستخدم.
- لا ترسل seed phrase أو private key أو كلمات المرور إلى Al-Manara أو أي شخص يدعي تمثيلها.

<b>3. التوثيق والخصوصية</b>
يتطلب استخدام الطلبات توثيق الحساب، وقد يشمل رقم الهاتف المشارك من Telegram، والاسم الكامل، وبيانات حساب ShamCash وعنوان الاستلام وQR المرتبط به. تتم مطابقة بيانات QR والعنوان آلياً حيثما أمكن، وقد تخضع طلبات التوثيق لمراجعة إدارية قبل تفعيل الحساب.

تستخدم بيانات التوثيق لأغراض التحقق من الحساب، ومنع انتحال الهوية والاحتيال، وحماية الحسابات والطلبات، وتنفيذ ومراجعة الطلبات، والإجراءات القانونية اللازمة عند وجود احتيال أو إساءة استخدام أو طلب قانوني ملزم.

لا تستخدم بيانات التوثيق لأغراض تسويقية، ولا تباع أو تشارك تجارياً مع أطراف ثالثة. يقتصر الوصول إليها على الصلاحيات اللازمة للعمل، وتخضع الإجراءات الإدارية الحساسة لسجلات التدقيق.

قد نحتفظ ببعض البيانات بالقدر اللازم للأمن أو المحاسبة أو المتطلبات القانونية أو لمنع الاحتيال وحماية الحقوق؛ لذلك لا يعني طلب حذف الحساب حذف السجلات التي يجب الاحتفاظ بها لهذه الأسباب.

<b>4. الدفع والمعاملات</b>
- يتم الدفع عبر وسائل ShamCash المعتمدة التي يعرضها البوت.
- لا ترسل أي مبلغ قبل ظهور تعليمات الدفع الرسمية داخل مسار الطلب وبعد أن يصبح الطلب جاهزاً للدفع.
- لا تعتمد على تعليمات تصل عبر رسالة خاصة أو قناة غير رسمية.
- يثبت عند إنشاء الطلب المبلغ وسعر الصرف والرسوم وعملة الدفع وبيانات وسيلة الدفع المطلوبة للطلب ضمن snapshot.
- قد ترفض الطلبات التي لا تستوفي متطلبات التحقق أو الدفع أو مكافحة الاحتيال.
- إذا لم تحصل على تعليمات الدفع الرسمية من مسار الطلب، لا تفترض أن أي بيانات تحويل خارجية تخص Al-Manara.

<b>5. الطلبات والمعالجة</b>
- يتم إنشاء الطلب بعد اكتمال متطلبات الحساب والمحفظة والبيانات اللازمة.
- قد يخضع الطلب لمراجعة إدارية قبل السماح بالدفع، وفق حالة الحساب والطلب.
- لا تعتبر المعاملة مكتملة لمجرد إنشاء الطلب؛ تمر عبر حالات معالجة محددة حتى تأكيد الدفع وإرسال USDT.
- بيانات الطلب الأساسية تثبت عند إنشائه لمنع تغييرها بشكل غير متوقع أثناء المعالجة.
- يجب رفع إثبات الدفع عبر المسار الرسمي المخصص للطلب عندما يُطلب ذلك.
- لا تنشئ طلباً جديداً للتحايل على طلب نشط؛ إذا كان لديك طلب نشط، استخدم مسار «طلباتي» لمتابعته.

<b>6. الأمان ومكافحة الاحتيال</b>
لن نطلب منك عبر رسالة خاصة تحويل الأموال إلى عنوان خارجي، أو إرسال seed phrase أو private key أو كلمة مرور، أو تجاوز مسار الدفع الرسمي. إذا طلب منك أي شخص ذلك، فلا تنفذ الطلب وأبلغ الدعم عبر القنوات الرسمية.

لا يستطيع النظام حماية أصولك إذا فقدت السيطرة على Telegram أو محفظتك أو بيانات الوصول إليها. تأكد من استخدام حساب Telegram والمحفظة الخاصة بك، ومن عدم مشاركة رموز الدخول أو بيانات الاسترداد.

<b>7. التحديثات والاحتفاظ بالسجلات</b>
قد يتم تحديث الشروط عند الحاجة الأمنية أو التشغيلية أو القانونية. عند وجود تغيير جوهري، يتم عرضه للمستخدم قبل استمرار الاستخدام وفق ما يتطلبه النظام.

قد تحتفظ Al-Manara بسجلات المعاملات والتدقيق بالقدر اللازم للأمن والمحاسبة ومكافحة الاحتيال والالتزامات القانونية، حتى عند طلب حذف الحساب.

━━━━━━━━━━━━━━━━━━━━
<b>هذه الوثيقة هي المرجع الكامل للشروط والسياسات. يمكنك فتح كل قسم منها منفرداً من مركز الشروط والسياسات داخل لوحة العميل.</b>""",
    "en": """━━━ <b>Complete Terms & Policies</b> ━━━

<b>1. Service Nature & Protection</b>
Al-Manara is a technical interface for managing USDT purchase orders and payments through approved ShamCash methods. It does not custody digital assets and never asks for a private key, seed phrase, or wallet password, nor does it ask you to transfer funds outside the official order flow.

The service uses multiple validation layers before an order is fixed, including account data, phone verification, the registered wallet, network, receiving address, and linked wallet QR, followed by a consistency check when the order is created. When the wallet belongs to you, is secure, and the information provided is correct, these controls can bring address and network input errors close to zero, without being an absolute guarantee against asset loss or account compromise.

<b>2. Wallet & Receiving Address</b>
- The wallet must belong to you and its account and access credentials must remain secure.
- You are responsible for confirming the receiving address and network you intend to use.
- The address, network, and linked QR are validated before the wallet can be used for an order.
- The stored QR is used as an additional verification of the receiving-address identity.
- The system cannot prove wallet ownership from an address alone; ownership and account security remain your responsibility.
- Never send a seed phrase, private key, or password to Al-Manara or anyone claiming to represent it.

<b>3. Verification & Privacy</b>
Using orders requires account verification, which may include the phone number shared from Telegram, full name, ShamCash receiving-account data, receiving address, and linked QR. QR/address values are matched automatically where possible, and verification requests may be reviewed by administrators before account activation.

Verification data is used for account verification, preventing impersonation and fraud, protecting accounts and orders, processing and reviewing orders, and necessary legal procedures in cases of fraud, abuse, or a binding legal request.

Verification data is not used for marketing, sold, or commercially shared with third parties. Access is limited to operational needs, and sensitive administrative actions are recorded in audit logs.

Some data may be retained when necessary for security, accounting, legal requirements, fraud prevention, or protection of rights; therefore an account-deletion request does not require deletion of records that must be retained for those reasons.

<b>4. Payments & Transactions</b>
- Payments are made through approved ShamCash methods shown by the bot.
- Do not send any payment before official payment instructions appear inside the order flow and the order is ready for payment.
- Do not rely on instructions received through private messages or unofficial channels.
- The order snapshot fixes the amount, exchange rate, fees, payment currency, and payment-method data required for the order when it is created.
- Orders may be rejected when verification, payment, or anti-fraud requirements are not met.
- If official payment instructions have not appeared in the order flow, do not assume external transfer details belong to Al-Manara.

<b>5. Orders & Processing</b>
- An order is created after account, wallet, and required data requirements are satisfied.
- An order may undergo administrative review before payment is allowed, depending on account and order status.
- Creating an order does not mean the transaction is complete; it passes through defined processing states until payment is confirmed and USDT is sent.
- Core order data is fixed when the order is created to prevent unexpected changes during processing.
- Upload payment proof through the official order flow when requested.
- Do not create another order to bypass an active order; use Orders to follow the existing one.

<b>6. Security & Anti-Fraud</b>
We will not ask you through private messages to transfer funds to an external address, send a seed phrase, private key, or password, or bypass the official payment flow. If anyone asks you to do so, do not proceed and report it through official support channels.

The system cannot protect your assets if you lose control of Telegram, your wallet, or their access credentials. Use your own Telegram account and wallet and never share login or recovery data.

<b>7. Updates & Record Retention</b>
These terms may be updated when required for security, operations, or legal compliance. Material changes will be presented before continued use when required by the system.

Al-Manara may retain transaction and audit records as necessary for security, accounting, fraud prevention, and legal obligations, including after an account-deletion request.

━━━━━━━━━━━━━━━━━━━━
<b>This document is the complete terms and policy reference. Each section can be opened separately from the Terms & Policies Center in the customer panel.</b>""",
}


def get_terms_text(lang: str, timeout: int) -> str:
    """Return the complete canonical terms/privacy text."""
    return TERMS_TEXT.get(lang, TERMS_TEXT["ar"])


def get_start_terms_text(lang: str, timeout: int) -> str:
    """Return the concise terms required for first-time onboarding."""
    return START_TERMS_TEXT.get(lang, START_TERMS_TEXT["ar"])
