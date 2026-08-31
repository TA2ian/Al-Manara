"""Canonical customer-facing order invoice and payment summary."""
from __future__ import annotations

from datetime import datetime

from services.formatters import money, rate, usdt


def render_order_invoice(*, order_number: str, requested_amount_usdt_value, amount_usdt_value, network: str, wallet: str, currency: str, exchange_rate_value, base_amount_value, fee_percent_value, fee_amount_value, total_value, payment_deadline: datetime | None = None, lang: str = "ar", service_fee_usdt_value=None, fixed_network_fee_usdt_value=None, total_fee_usdt_value=None) -> str:
    service_fee_usdt = usdt(service_fee_usdt_value or 0)
    fixed_network_fee_usdt = usdt(fixed_network_fee_usdt_value or 0)
    total_fee_usdt = usdt(total_fee_usdt_value if total_fee_usdt_value is not None else (fee_amount_value or 0))
    fee_percent = usdt(fee_percent_value or 0)
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
            f"• Order value before fees: <b>{money(base_amount_value)} {currency}</b>\n"
            f"• Service fee: <b>{service_fee_usdt} USDT ({fee_percent_value or 0}%)</b>\n"
            f"• Fixed network fee: <b>{fixed_network_fee_usdt} USDT</b>\n"
            f"• Total fees: <b>{total_fee_usdt} USDT</b>\n"
            f"• Total fees in payment currency: <b>{money(fee_amount_value)} {currency}</b>\n"
            f"• Amount to pay: <b>{money(total_value)} {currency}</b>\n\n"
            "The displayed fees are based on the selected network policy. The TXID verification tolerance is separate and is not a fee.\n\n"
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
        f"• رسوم الخدمة: <b>{service_fee_usdt} USDT ({fee_percent_value or 0}%)</b>\n"
        f"• الرسم الثابت للشبكة: <b>{fixed_network_fee_usdt} USDT</b>\n"
        f"• إجمالي الرسوم: <b>{total_fee_usdt} USDT</b>\n"
        f"• إجمالي الرسوم بعملة الدفع: <b>{money(fee_amount_value)} {currency}</b>\n"
        f"• المبلغ المطلوب دفعه: <b>{money(total_value)} {currency}</b>\n\n"
        "ℹ️ الرسوم تعتمد على سياسة الشبكة المحددة من الإدارة. هامش التحقق من TXID بقيمة ±0.04 USDT منفصل عن الرسوم ولا يُخصم من استحقاقك.\n\n"
        "<b>ماذا يحدث بعد ذلك؟</b>\n"
        "يراجع الطلب أولاً، وبعد اعتماده ستصلك بيانات الدفع الرسمية. <b>لا ترسل أي مبلغ قبل الاعتماد.</b>\n"
        f"• مهلة الدفع: <b>{deadline}</b>\n\n"
        "🔐 تأكد من الشبكة وعنوان محفظتك قبل تأكيد الطلب."
    )
