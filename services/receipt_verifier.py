"""OCR-based ShamCash receipt verification."""
import asyncio
import io
import logging
import re
import time
from datetime import datetime

from PIL import Image, ImageOps
import pytesseract

from services.formatters import money

logger = logging.getLogger(__name__)
OCR_TIMEOUT_SECONDS = 15
OCR_MAX_DIMENSION = 1400


class ReceiptVerifier:
    """Analyze receipts and calculate a review confidence score."""

    @staticmethod
    def _ocr_sync(image_bytes: bytes) -> str:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image = ImageOps.exif_transpose(image)
        image.thumbnail((OCR_MAX_DIMENSION, OCR_MAX_DIMENSION), Image.Resampling.LANCZOS)
        grayscale = ImageOps.grayscale(image)
        grayscale = ImageOps.autocontrast(grayscale)
        return pytesseract.image_to_string(
            grayscale,
            lang="ara+eng",
            config="--psm 6 --oem 3",
            timeout=OCR_TIMEOUT_SECONDS,
        )

    @staticmethod
    async def _ocr(image_bytes: bytes) -> str:
        """Run CPU-bound Tesseract work outside the asyncio event loop."""
        started = time.perf_counter()
        try:
            return await asyncio.to_thread(ReceiptVerifier._ocr_sync, image_bytes)
        finally:
            elapsed = time.perf_counter() - started
            logger.info("receipt_ocr_completed elapsed_seconds=%.3f bytes=%d", elapsed, len(image_bytes))

    @staticmethod
    async def analyze_receipt(image_bytes: bytes, expected_amount: float) -> dict:
        try:
            text = await ReceiptVerifier._ocr(image_bytes)
            amounts = ReceiptVerifier._extract_amounts(text)
            has_text = bool(text.strip())
            tolerance = float(expected_amount) * 0.02
            matched_amount = next((a for a in amounts if abs(a - float(expected_amount)) <= tolerance), None)
            amount_match = matched_amount is not None

            if amount_match and has_text:
                confidence = "high"
                message = f"✅ تم التحقق آلياً: المبلغ {money(matched_amount)} مطابق للقيمة المتوقعة {money(expected_amount)}"
            elif has_text and amounts:
                confidence = "medium"
                nearest = min(amounts, key=lambda x: abs(x - float(expected_amount)))
                message = f"⚠️ تطابق جزئي: الأقرب {money(nearest)} بينما المتوقع {money(expected_amount)}"
            elif has_text:
                confidence = "low"
                message = "⚠️ تم العثور على نص لكن لم يتم التعرف على مبلغ واضح"
            else:
                confidence = "none"
                message = "❌ لم يتم التعرف على نص في الإيصال"

            return {"success": True, "text": text[:1000], "extracted_amounts": amounts, "amount_match": amount_match, "has_text": has_text, "confidence": confidence, "message": message, "matched_amount": matched_amount}
        except Exception as exc:
            logger.exception("Receipt analysis failed")
            return {"success": False, "text": "", "extracted_amounts": [], "amount_match": False, "has_text": False, "confidence": "error", "message": f"❌ فشل تحليل الصورة: {exc}", "matched_amount": None}

    @staticmethod
    def _extract_amounts(text: str) -> list[float]:
        amounts = []
        patterns = [
            r"\b\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\b",
            r"(?:USDT|USD|SYP|ل\.س|دولار|ليرة|ريال|₪|\$)\s*[:\s]*([\d,]+\.?\d*)",
            r"(?:المجموع|الإجمالي|المبلغ|total|amount|مجموع|payment|قيمة)\D*([\d,]+\.?\d*)",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                value = match if isinstance(match, str) else match[-1]
                try:
                    number = float(value.replace(",", ""))
                    if 0.1 <= number <= 1_000_000:
                        amounts.append(number)
                except (TypeError, ValueError):
                    continue
        return sorted(set(round(a, 2) for a in amounts))

    @staticmethod
    async def verify_shamcash_receipt(image_bytes: bytes, order_date: datetime, customer_name: str, customer_shamcash_account: str, admin_name: str, admin_shamcash_account: str, expected_amount: float, payment_currency: str = "USD") -> dict:
        """Compare receipt date, identities, accounts and amount without auto-completing payment."""
        started = time.perf_counter()
        try:
            text = await ReceiptVerifier._ocr(image_bytes)
            extracted = ReceiptVerifier._extract_shamcash_fields(text)
            expected_date = order_date.strftime("%Y-%m-%d") if order_date else ""
            matches = {
                "date": ReceiptVerifier._date_matches(extracted.get("date", ""), expected_date),
                "sender_name": ReceiptVerifier._name_matches(extracted.get("sender_name", ""), customer_name),
                "sender_account": ReceiptVerifier._compare_masked_account(extracted.get("sender_account", ""), customer_shamcash_account),
                "recipient_name": ReceiptVerifier._name_matches(extracted.get("recipient_name", ""), admin_name),
                "recipient_account": ReceiptVerifier._compare_masked_account(extracted.get("recipient_account", ""), admin_shamcash_account),
                "amount": False,
            }
            extracted_amount = float(extracted.get("amount") or 0)
            expected = float(expected_amount or 0)
            if extracted_amount > 0 and expected > 0:
                matches["amount"] = abs(extracted_amount - expected) <= expected * 0.02

            details = [
                f"{'✅' if matches['date'] else '❌'} التاريخ: {extracted.get('date') or 'غير معروف'}",
                f"{'✅' if matches['sender_name'] else '❌'} اسم المرسل: {extracted.get('sender_name') or 'غير معروف'}",
                f"{'✅' if matches['sender_account'] else '❌'} حساب المرسل: {extracted.get('sender_account') or 'غير معروف'}",
                f"{'✅' if matches['recipient_name'] else '❌'} اسم المستلم: {extracted.get('recipient_name') or 'غير معروف'}",
                f"{'✅' if matches['recipient_account'] else '❌'} حساب المستلم: {extracted.get('recipient_account') or 'غير معروف'}",
                f"{'✅' if matches['amount'] else '❌'} المبلغ: {money(extracted_amount)} {'✓ مطابق للقيمة المتوقعة ' + money(expected) if matches['amount'] else '≠ ' + money(expected)}",
            ]
            weights = {"date": 20, "sender_name": 15, "sender_account": 15, "recipient_name": 10, "recipient_account": 10, "amount": 30}
            score = sum(weight for key, weight in weights.items() if matches.get(key))
            score_label = "عالية" if score >= 80 else "متوسطة" if score >= 50 else "منخفضة" if score > 0 else "فاشل"
            summary = "━━━ 🔍 نتيجة التحقق الآلي من إيصال شام كاش ━━━\n\n" f"✅ المطابقة: {sum(matches.values())}/{len(matches)} حقلاً\n" f"📊 نسبة الثقة: {score}% ({score_label})\n\n" + "\n".join(details)
            return {"success": True, "text": text[:1000], "fields": extracted, "matches": matches, "score": score, "score_label": score_label, "summary": summary, "details": details, "auto_verified": score >= 80, "matched_amount": extracted_amount if matches["amount"] else None, "payment_currency": payment_currency}
        except Exception as exc:
            logger.exception("ShamCash receipt verification failed")
            return {"success": False, "text": "", "fields": {}, "matches": {}, "score": 0, "score_label": "فاشل", "summary": f"❌ فشل تحليل الإيصال: {exc}", "details": [f"❌ خطأ تقني: {exc}"], "auto_verified": False, "matched_amount": None, "payment_currency": payment_currency}
        finally:
            logger.info("receipt_verification_completed elapsed_seconds=%.3f", time.perf_counter() - started)

    @staticmethod
    def _extract_shamcash_fields(text: str) -> dict:
        result = {"date": "", "sender_name": "", "sender_account": "", "recipient_name": "", "recipient_account": "", "amount": 0.0}
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        date_match = re.search(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})", text)
        if date_match:
            result["date"] = date_match.group(1)
        for i, line in enumerate(lines):
            if "اسم المرسل" in line or re.search(r"\bSender\b", line, re.IGNORECASE):
                result["sender_name"] = ReceiptVerifier._label_value(line, r"اسم المرسل|Sender") or (lines[i + 1] if i + 1 < len(lines) else "")
            if "اسم المستلم" in line or "المستلم" in line:
                result["recipient_name"] = ReceiptVerifier._label_value(line, r"اسم المستلم|المستلم") or (lines[i + 1] if i + 1 < len(lines) else "")
            if "حساب المرسل" in line:
                result["sender_account"] = re.sub(r"[^\d*]", "", ReceiptVerifier._label_value(line, r"حساب المرسل"))
            if "حساب المستلم" in line:
                result["recipient_account"] = re.sub(r"[^\d*]", "", ReceiptVerifier._label_value(line, r"حساب المستلم"))
            if "المبلغ" in line or re.search(r"\bamount\b", line, re.IGNORECASE):
                amount_match = re.search(r"([\d,]+(?:\.\d+)?)", line)
                if amount_match:
                    try:
                        result["amount"] = float(amount_match.group(1).replace(",", ""))
                    except ValueError:
                        pass
        masked = re.findall(r"(\d{3,}\*+)", text)
        if not result["sender_account"] and masked:
            result["sender_account"] = masked[0]
        if not result["recipient_account"] and len(masked) > 1:
            result["recipient_account"] = masked[1]
        if not result["amount"]:
            amount_match = re.search(r"(?:\$|SYP|USD|NEW\.SYP)\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
            if amount_match:
                result["amount"] = float(amount_match.group(1).replace(",", ""))
        return result

    @staticmethod
    def _label_value(line: str, labels: str) -> str:
        return re.sub(rf"(?:{labels})\s*[:：]?\s*", "", line, flags=re.IGNORECASE).strip()

    @staticmethod
    def _date_matches(extracted: str, expected: str) -> bool:
        if not extracted or not expected:
            return False
        normalized = extracted.replace("/", "-")
        if normalized == expected:
            return True
        parts = normalized.split("-")
        return len(parts) == 3 and f"{parts[2]}-{parts[1]}-{parts[0]}" == expected

    @staticmethod
    def _name_matches(extracted: str, expected: str) -> bool:
        if not extracted or not expected:
            return False
        a, b = ReceiptVerifier._normalize_arabic(extracted), ReceiptVerifier._normalize_arabic(expected)
        if a == b or a in b or b in a:
            return True
        overlap = set(a.split()) & set(b.split())
        return bool(overlap) and len(overlap) / max(len(set(a.split())), len(set(b.split()))) >= 0.5

    @staticmethod
    def _normalize_arabic(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[أإآا]", "ا", text)
        text = re.sub(r"[ةۀ]", "ه", text)
        text = re.sub(r"[ؤ]", "و", text)
        text = re.sub(r"[\u064B-\u065Fـ]", "", text)
        return re.sub(r"\s+", " ", text.strip()).lower()

    @staticmethod
    def _compare_masked_account(extracted: str, expected: str) -> bool:
        if not extracted or not expected:
            return False
        extracted_digits, expected_digits = re.sub(r"[^\d]", "", extracted), re.sub(r"[^\d]", "", expected)
        if not extracted_digits or not expected_digits:
            return False
        if extracted_digits == expected_digits:
            return True
        if len(extracted_digits) >= len(expected_digits):
            return False
        prefix_len, suffix_len = min(4, len(extracted_digits), len(expected_digits)), min(4, len(extracted_digits), len(expected_digits))
        return extracted_digits[:prefix_len] == expected_digits[:prefix_len] or extracted_digits[-suffix_len:] == expected_digits[-suffix_len:]