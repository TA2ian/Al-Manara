"""Canonical customer-facing order invoice and payment summary."""
from __future__ import annotations

from datetime import datetime

from services.formatters import money, percent, rate, usdt


def render_order_invoice(*, order_number: str, requested_amount_usdt_value, amount_usdt_value, network: str, wallet: str, currency: str, exchange_rate_value, base_amount_value, fee_percent_value, fee_amount_value, total_value, payment_deadline: datetime | None = None, lang: str = "ar") -> str:
    if lang == "en":
        deadline = payment_deadline.strftime("%Y-%m-%d %H:%M") if payment_deadline else "After order approval"
        return (
            f"🧾 <b>Order Invoice · #{order_number}</b>\n\n"
            "<b>Your request</b>\n"
            f"• Amount entered: <b>{usdt(requested_amount_usdt_value)} USDT</b>\n"
            f"• You receive: <b>{usdt(amount_usdt_value)} USDT</b>\n"
            f"• Network: <b>{network}</b>\n"
            f"• Receiving wallet: <code>{wallet}</code>\n\n"
            "<b>Payment calculation</b>\n"
            f"• Currency: <b>{currency}</b>\n"
            f"• Exchange rate: <b>{rate(exchange_rate_value)}</b>\n"
            f"• Order value: <b>{money(base_amount_value)} {currency}</b>\n"
            f"• Service fee ({percent(fee_percent_value)}%): <b>{money(fee_amount_value)} {currency}</b>\n"
            f"• Amount to pay: <b>{money(total_value)} {currency}</b>\n\n"
            "The service fee is deducted from the amount you entered; it is not added on top.\n\n"
            "<b>What happens next?</b>\n"
            "Your request is reviewed before official payment details are issued. Do not transfer funds before approval.\n"
            f"• Payment deadline: <b>{deadline}</b>\n\n"
            "🔐 Verify the network and receiving wallet before confirming."
        )

    deadline = payment_deadline.strftime("%Y-%m-%d %H:%M") if payment_deadline else "بعد اعتماد الطلب"
    return (
        f"🧾 <b>فاتورة طلبك · #{order_number}</b>\n\n"
        "<b>تفاصيل طلبك</b>\n"
        f"• المبلغ الذي حددته: <b>{usdt(requested_amount_usdt_value)} USDT</b>\n"
        f"• المبلغ الذي سيصلك: <b>{usdt(amount_usdt_value)} USDT</b>\n"
        f"• الشبكة: <b>{network}</b>\n"
        f"• محفظة الاستلام: <code>{wallet}</code>\n\n"
        "<b>حساب المبلغ</b>\n"
        f"• عملة الدفع: <b>{currency}</b>\n"
        f"• سعر الصرف: <b>{rate(exchange_rate_value)}</b>\n"
        f"• قيمة الطلب قبل الرسوم: <b>{money(base_amount_value)} {currency}</b>\n"
        f"• رسوم الخدمة ({percent(fee_percent_value)}%): <b>{money(fee_amount_value)} {currency}</b>\n"
        f"• المبلغ المطلوب دفعه: <b>{money(total_value)} {currency}</b>\n\n"
        "ℹ️ رسوم الخدمة تُخصم من المبلغ الذي حددته ولا تُضاف فوقه.\n\n"
        "<b>ماذا يحدث بعد ذلك؟</b>\n"
        "يراجع الطلب أولاً، وبعد اعتماده ستصلك بيانات الدفع الرسمية. <b>لا ترسل أي مبلغ قبل الاعتماد.</b>\n"
        f"• مهلة الدفع: <b>{deadline}</b>\n\n"
        "🔐 تأكد من الشبكة وعنوان محفظتك قبل تأكيد الطلب."
    )
