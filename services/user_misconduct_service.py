"""Confirmed payment-receipt manipulation policy and suspension lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


FIRST_INCIDENT_SUSPENSION_HOURS = 4
SECOND_INCIDENT_SUSPENSION_HOURS = 24
MAX_CONFIRMED_INCIDENTS = 3


@dataclass(frozen=True)
class MisconductDecision:
    """Authoritative consequence produced by a confirmed manipulation incident."""

    incident_number: int
    suspension_expires_at: datetime | None
    requires_admin_review: bool
    final_warning: bool


async def confirm_manipulation(
    conn,
    *,
    user_id: int,
    telegram_id: int,
    order_id: int,
    admin_id: int,
    reason: str = "confirmed_payment_receipt_manipulation",
) -> MisconductDecision:
    """Record one explicit admin-confirmed manipulation incident atomically."""
    user = await conn.fetchrow(
        "SELECT id, telegram_id, is_blocked FROM users WHERE id = $1 FOR UPDATE",
        user_id,
    )
    if not user:
        raise ValueError("customer does not exist")
    if int(user["telegram_id"]) != int(telegram_id):
        raise ValueError("customer identity mismatch")

    existing_count = await conn.fetchval(
        "SELECT COUNT(*) FROM misconduct_incidents WHERE user_id = $1",
        user_id,
    )
    incident_number = int(existing_count) + 1
    if incident_number > MAX_CONFIRMED_INCIDENTS:
        raise ValueError("customer already reached the final confirmed manipulation incident")

    if incident_number == 1:
        suspension_expires_at = datetime.utcnow() + timedelta(hours=FIRST_INCIDENT_SUSPENSION_HOURS)
        requires_admin_review = False
        final_warning = False
        suspension_reason = "confirmed manipulation: 4-hour service suspension"
    elif incident_number == 2:
        suspension_expires_at = datetime.utcnow() + timedelta(hours=SECOND_INCIDENT_SUSPENSION_HOURS)
        requires_admin_review = True
        final_warning = False
        suspension_reason = "confirmed manipulation: 24-hour service suspension and admin review"
    else:
        suspension_expires_at = None
        requires_admin_review = True
        final_warning = True
        suspension_reason = "confirmed manipulation: final incident, account suspended pending admin decision"

    await conn.execute(
        """
        INSERT INTO misconduct_incidents
            (user_id, telegram_id, order_id, admin_id, incident_number, reason, suspension_expires_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        user_id,
        telegram_id,
        order_id,
        admin_id,
        incident_number,
        reason,
        suspension_expires_at,
    )
    await conn.execute("DELETE FROM blocked_users WHERE telegram_id = $1", telegram_id)
    await conn.execute(
        "INSERT INTO blocked_users (telegram_id, reason, blocked_by, expires_at) VALUES ($1, $2, $3, $4)",
        telegram_id,
        suspension_reason,
        admin_id,
        suspension_expires_at,
    )
    await conn.execute(
        "UPDATE users SET is_blocked = $1 WHERE id = $2",
        incident_number >= MAX_CONFIRMED_INCIDENTS,
        user_id,
    )
    await conn.execute(
        """
        INSERT INTO audit_logs (user_id, admin_id, action, details, severity)
        VALUES ($1, $2, 'confirmed_receipt_manipulation', $3, $4)
        """,
        user_id,
        admin_id,
        f"Confirmed manipulation incident #{incident_number} for order {order_id}; suspension_expires_at={suspension_expires_at!s}",
        "critical" if incident_number >= MAX_CONFIRMED_INCIDENTS else "warning",
    )

    return MisconductDecision(
        incident_number=incident_number,
        suspension_expires_at=suspension_expires_at,
        requires_admin_review=requires_admin_review,
        final_warning=final_warning,
    )


async def clear_suspension(conn, *, telegram_id: int, admin_id: int, decision: str) -> None:
    """Allow a third-incident customer to continue after final admin review."""
    await conn.execute("UPDATE users SET is_blocked = FALSE WHERE telegram_id = $1", telegram_id)
    await conn.execute("DELETE FROM blocked_users WHERE telegram_id = $1", telegram_id)
    await conn.execute(
        """
        INSERT INTO audit_logs (user_id, admin_id, action, details, severity)
        SELECT id, $2, 'misconduct_review_cleared', $3, 'warning'
        FROM users WHERE telegram_id = $1
        """,
        telegram_id,
        admin_id,
        f"Administrative decision after final manipulation review: {decision}",
    )


async def permanent_ban(conn, *, telegram_id: int, admin_id: int, reason: str) -> None:
    """Convert the final suspension into an explicit permanent administrative ban."""
    user = await conn.fetchrow(
        "SELECT id FROM users WHERE telegram_id = $1 FOR UPDATE",
        telegram_id,
    )
    if not user:
        raise ValueError("customer does not exist")
    incident_count = await conn.fetchval(
        "SELECT COUNT(*) FROM misconduct_incidents WHERE user_id = $1",
        user["id"],
    )
    if int(incident_count) < MAX_CONFIRMED_INCIDENTS:
        raise ValueError("permanent ban requires three confirmed manipulation incidents")

    await conn.execute("UPDATE users SET is_blocked = TRUE WHERE id = $1", user["id"])
    await conn.execute("DELETE FROM blocked_users WHERE telegram_id = $1", telegram_id)
    await conn.execute(
        "INSERT INTO blocked_users (telegram_id, reason, blocked_by, expires_at) VALUES ($1, $2, $3, NULL)",
        telegram_id,
        reason,
        admin_id,
    )
    await conn.execute(
        """
        INSERT INTO audit_logs (user_id, admin_id, action, details, severity)
        VALUES ($1, $2, 'misconduct_permanent_ban', $3, 'critical')
        """,
        user["id"],
        admin_id,
        reason,
    )


async def get_suspension(conn, telegram_id: int):
    """Return the effective suspension, cleaning up expired temporary rows."""
    await conn.execute(
        "DELETE FROM blocked_users WHERE telegram_id = $1 AND expires_at IS NOT NULL AND expires_at <= NOW()",
        telegram_id,
    )
    return await conn.fetchrow(
        """
        SELECT u.is_blocked, b.reason, b.expires_at
        FROM users u
        LEFT JOIN LATERAL (
            SELECT reason, expires_at
            FROM blocked_users
            WHERE telegram_id = $1
            ORDER BY blocked_at DESC, id DESC
            LIMIT 1
        ) b ON TRUE
        WHERE u.telegram_id = $1
        """,
        telegram_id,
    )


def customer_notice(decision: MisconductDecision, lang: str) -> str:
    """Render the customer-facing consequence without exposing internal admin data."""
    if lang == "en":
        if decision.incident_number == 1:
            return (
                "🚫 <b>Service temporarily suspended</b>\n\n"
                "Administration confirmed an attempted payment-receipt manipulation after your available receipt-verification attempts were exhausted.\n\n"
                "Your service is suspended for <b>4 hours</b>. Please use accurate payment information and submit the correct receipt when service is restored."
            )
        if decision.incident_number == 2:
            return (
                "🚫 <b>Service suspended for review</b>\n\n"
                "Administration confirmed a second payment-receipt manipulation incident.\n\n"
                "Your service is suspended for <b>24 hours</b> and the account is flagged for administrative review. Further confirmed manipulation may result in permanent account action."
            )
        return (
            "🛑 <b>Account suspended pending final review</b>\n\n"
            "Administration confirmed a third payment-receipt manipulation incident.\n\n"
            "This is your <b>final warning</b>. Your account is suspended until an administrator decides whether service will continue or the account will be permanently banned."
        )

    if decision.incident_number == 1:
        return (
            "🚫 <b>تم تعليق الخدمة مؤقتاً</b>\n\n"
            "أكدت الإدارة وجود محاولة تلاعب في إثبات الدفع بعد استنفاد محاولات التحقق المتاحة لإرسال إيصال صحيح.\n\n"
            "تم تعليق خدمتك لمدة <b>4 ساعات</b>. عند عودة الخدمة، أرسل بيانات الدفع الصحيحة والإيصال المطابق فقط."
        )
    if decision.incident_number == 2:
        return (
            "🚫 <b>تم تعليق الخدمة للمراجعة</b>\n\n"
            "أكدت الإدارة وجود محاولة تلاعب ثانية في إثبات الدفع.\n\n"
            "تم تعليق خدمتك لمدة <b>24 ساعة</b> وإحالة الحساب للمراجعة الإدارية. أي محاولة تلاعب أخرى مؤكدة قد تؤدي إلى اتخاذ إجراء دائم على الحساب."
        )
    return (
        "🛑 <b>تم تعليق الحساب بانتظار القرار النهائي</b>\n\n"
        "أكدت الإدارة وجود محاولة تلاعب ثالثة في إثبات الدفع.\n\n"
        "هذه <b>الفرصة الأخيرة</b>. سيبقى حسابك معلقاً إلى أن يقرر الأدمن استمرار الخدمة أو حظر الحساب نهائياً."
    )


def suspension_notice(reason: str | None, expires_at: datetime | None, lang: str) -> str:
    """Render the current suspension status for a blocked customer."""
    if expires_at is None:
        return (
            "🛑 <b>حسابك معلق حالياً</b>\n\n"
            "الخدمات متوقفة إلى أن يصدر قرار إداري نهائي بشأن الحساب.\n\n"
            "إذا كان لديك اعتراض، استخدم قناة الدعم."
            if lang == "ar" else
            "🛑 <b>Your account is currently suspended</b>\n\n"
            "Services are disabled until a final administrative decision is made.\n\n"
            "If you believe this is an error, contact support."
        )

    remaining_seconds = max(0, int((expires_at - datetime.utcnow()).total_seconds()))
    hours, remainder = divmod(remaining_seconds, 3600)
    minutes = (remainder + 59) // 60
    duration = f"{hours} ساعة و{minutes} دقيقة" if lang == "ar" else f"{hours}h {minutes}m"
    return (
        "🚫 <b>الخدمة معلقة مؤقتاً</b>\n\n"
        f"يمكنك استخدام الخدمة مجدداً بعد انتهاء التعليق المتبقي: <b>{duration}</b>."
        if lang == "ar" else
        "🚫 <b>Service temporarily suspended</b>\n\n"
        f"You can use the service again after the remaining suspension: <b>{duration}</b>."
    )
