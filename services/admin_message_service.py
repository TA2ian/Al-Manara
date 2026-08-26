"""Canonical admin-to-customer messaging and broadcast templates."""
from __future__ import annotations

from dataclasses import dataclass
import html


@dataclass(frozen=True)
class MessageTemplate:
    key: str
    title_ar: str
    title_en: str
    intro_ar: str
    intro_en: str
    footer_ar: str
    footer_en: str


TEMPLATES: dict[str, MessageTemplate] = {
    "update": MessageTemplate(
        "update", "تحديث من المنارة", "Al-Manara Update",
        "نشاركك آخر المستجدات التي قد تهمك:", "Here is an update that may be useful to you:",
        "شكراً لثقتك بالمنارة.", "Thank you for trusting Al-Manara.",
    ),
    "service": MessageTemplate(
        "service", "تنبيه خدمي", "Service Notice",
        "لدينا تنبيه متعلق بالخدمة:", "We have a service-related notice:",
        "إذا احتجت إلى مساعدة، يمكنك التواصل معنا من داخل البوت.", "If you need help, contact us from inside the bot.",
    ),
    "maintenance": MessageTemplate(
        "maintenance", "إشعار صيانة", "Maintenance Notice",
        "نقوم حالياً بإجراء تحديثات تشغيلية لتحسين الخدمة:", "We are performing operational maintenance to improve the service:",
        "سنعود إلى الوضع الطبيعي فور اكتمال العمل.", "We will return to normal operation as soon as the work is complete.",
    ),
    "important": MessageTemplate(
        "important", "تنبيه مهم", "Important Notice",
        "يرجى الانتباه إلى المعلومات التالية:", "Please note the following important information:",
        "يرجى الاعتماد على الرسائل الرسمية داخل البوت فقط.", "Please rely only on official messages inside the bot.",
    ),
}


def render_template(template_key: str, body: str, lang: str = "ar", *, recipient_name: str | None = None) -> str:
    template = TEMPLATES.get(template_key)
    if template is None:
        raise ValueError(f"Unknown message template: {template_key}")
    clean_body = body.strip()
    if not clean_body:
        raise ValueError("Message body cannot be empty")
    if len(clean_body) > 3500:
        raise ValueError("Message body exceeds the template limit")
    safe_body = html.escape(clean_body)
    if lang == "en":
        greeting = f"Hello {html.escape(recipient_name.strip())}," if recipient_name and recipient_name.strip() else "Hello,"
        return (
            f"📣 <b>{template.title_en}</b>\n\n{greeting}\n\n"
            f"{template.intro_en}\n\n{safe_body}\n\n"
            f"{template.footer_en}\n\n— <b>Al-Manara</b>"
        )
    greeting = f"مرحباً {html.escape(recipient_name.strip())}،" if recipient_name and recipient_name.strip() else "مرحباً،"
    return (
        f"📣 <b>{template.title_ar}</b>\n\n{greeting}\n\n"
        f"{template.intro_ar}\n\n{safe_body}\n\n"
        f"{template.footer_ar}\n\n— <b>المنارة</b>"
    )


def template_choices() -> tuple[tuple[str, str], ...]:
    return (
        ("update", "📢 تحديث"),
        ("service", "ℹ️ تنبيه خدمي"),
        ("maintenance", "🛠️ صيانة"),
        ("important", "⚠️ تنبيه مهم"),
    )
