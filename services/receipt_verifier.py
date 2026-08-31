"""OCR-based ShamCash receipt verification."""
from __future__ import annotations

import asyncio
import io
import logging
import re
import time
from datetime import datetime

from PIL import Image, ImageOps
import pytesseract

from services.formatters import money
from services.receipt_verification_policy import amounts_match

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
        return pytesseract.image_to_string(grayscale, lang="ara+eng", config="--psm 6 --oem 3", timeout=OCR_TIMEOUT_SECONDS)

    @staticmethod
    async def _ocr(image_bytes: bytes) -> str:
        """Run CPU-bound Tesseract work outside the asyncio event loop."""
        started = time.perf_counter()
        try:
            return await asyncio.to_thread(ReceiptVerifier._ocr_sync, image_bytes)
        finally:
            logger.info("receipt_ocr_completed elapsed_seconds=%.3f bytes=%d", time.perf_counter() - started, len(image_bytes))

    @staticmethod
    def _normalize_ocr_text(text: str) -> str:
        if not text:
            return ""
        translation = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
        return text.translate(translation).replace("٫", ".").replace("٬", ",").replace("：", ":")

    @staticmethod
    def _numeric_value(value: str) -> float | None:
        if not value:
            return None
        normalized = ReceiptVerifier._normalize_ocr_text(value).replace(" ", "")
        if normalized.count(",") == 1 and normalized.count(".") == 0:
            left, right = normalized.split(",")
            normalized = f"{left}.{right}" if len(right) <= 2 else normalized.replace(",", "")
        else:
            normalized = normalized.replace(",", "")
        normalized = re.sub(r"[^0-9.]", "", normalized)
        if not normalized:
            return None
        try:
            number = float(normalized)
        except ValueError:
            return None
        return number if 0.1 <= number <= 1_000_000 else None

    @staticmethod
    async def analyze_receipt(image_bytes: bytes, expected_amount: float) -> dict:
        try:
            text = await ReceiptVerifier._ocr(image_bytes)
            amounts = ReceiptVerifier._extract_amounts(text)
            has_text = bool(text.strip())
            matched_amount = next((a for a in amounts if amounts_match(a, expected_amount)), None)
            amount_match = matched_amount is not None
            if amount_match and has_text:
                confidence, message = "high", f"✅ تم التحقق آلياً: المبلغ {money(matched_amount)} مطابق للقيمة المتوقعة {money(expected_amount)}"
            elif has_text and amounts:
                confidence = "medium"
                nearest = min(amounts, key=lambda x: abs(x - float(expected_amount)))
                message = f"⚠️ تطابق جزئي: الأقرب {money(nearest)} بينما المتوقع {money(expected_amount)}"
            elif has_text:
                confidence, message = "low", "⚠️ تم العثور على نص لكن لم يتم التعرف على مبلغ واضح"
            else:
                confidence, message = "none", "❌ لم يتم التعرف على نص في الإيصال"
            return {"success": True, "text": text[:1000], "extracted_amounts": amounts, "amount_match": amount_match, "has_text": has_text, "confidence": confidence, "message": message, "matched_amount": matched_amount}
        except Exception as exc:
            logger.exception("Receipt analysis failed")
            return {"success": False, "text": "", "extracted_amounts": [], "amount_match": False, "has_text": False, "confidence": "error", "message": f"❌ فشل تحليل الصورة: {exc}", "matched_amount": None}

    @staticmethod
    def _extract_amounts(text: str) -> list[float]:
        text = ReceiptVerifier._normalize_ocr_text(text)
        amounts: list[float] = []
        patterns = [
            r"\b\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\b",
            r"(?:USDT|USD|SYP|NEW\.SYP|ل\.س|دولار|ليرة|ريال|₪|\$)\s*[:\s]*([\d,]+(?:\.\d+)?)",
            r"(?:المجموع|الإجمالي|المبلغ|total|amount|مجموع|payment|قيمة|القيمة)\D*([\d,]+(?:\.\d+)?)",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                value = match if isinstance(match, str) else match[-1]
                number = ReceiptVerifier._numeric_value(value)
                if number is not None:
                    amounts.append(number)
        return sorted(set(round(a, 2) for a in amounts))

    @staticmethod
    async def verify_shamcash_receipt(image_bytes: bytes, order_date: datetime, customer_name: str, customer_shamcash_account: str, admin_name: str, admin_shamcash_account: str, expected_amount: float, payment_currency: str = "USD") -> dict:
        """Compare receipt date, identities, accounts and amount without auto-completing payment."""
        started = time.perf_counter()
        try:
            text = ReceiptVerifier._normalize_ocr_text(await ReceiptVerifier._ocr(image_bytes))
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
            matches["amount"] = amounts_match(extracted_amount, expected)
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
            core_matches = all(matches[key] for key in ("date", "sender_account", "recipient_account", "amount"))
            auto_verified = score >= 80 and core_matches
            summary = "━━━ 🔍 نتيجة التحقق الآلي من إيصال شام كاش ━━━\n\n" f"✅ المطابقة: {sum(matches.values())}/{len(matches)} حقلاً\n" f"📊 نسبة الثقة: {score}% ({score_label})\n\n" + "\n".join(details)
            return {"success": True, "text": text[:1000], "fields": extracted, "matches": matches, "score": score, "score_label": score_label, "summary": summary, "details": details, "auto_verified": auto_verified, "matched_amount": extracted_amount if matches["amount"] else None, "payment_currency": payment_currency}
        except Exception as exc:
            logger.exception("ShamCash receipt verification failed")
            return {"success": False, "text": "", "fields": {}, "matches": {}, "score": 0, "score_label": "فاشل", "summary": f"❌ فشل تحليل الإيصال: {exc}", "details": [f"❌ خطأ تقني: {exc}"], "auto_verified": False, "matched_amount": None, "payment_currency": payment_currency}
        finally:
            logger.info("receipt_verification_completed elapsed_seconds=%.3f", time.perf_counter() - started)

    @staticmethod
    def _extract_shamcash_fields(text: str) -> dict:
        text = ReceiptVerifier._normalize_ocr_text(text)
        result = {"date": "", "sender_name": "", "sender_account": "", "recipient_name": "", "recipient_account": "", "amount": 0.0}
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        date_match = re.search(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})", text)
        if date_match:
            result["date"] = date_match.group(1)
        sender_name_labels = r"اسم\s*المرسل|المرسل|sender|from"
        recipient_name_labels = r"اسم\s*المستلم|اسم\s*المستفيد|المستلم|المستفيد|recipient|beneficiary|to"
        sender_account_labels = r"حساب\s*المرسل|رقم\s*المرسل|حساب\s*الدافع|sender\s*(?:account|id)|from\s*(?:account|id)"
        recipient_account_labels = r"حساب\s*المستلم|رقم\s*المستلم|حساب\s*المستفيد|recipient\s*(?:account|id)|beneficiary\s*(?:account|id)|to\s*(?:account|id)"
        amount_labels = r"المبلغ|القيمة|الإجمالي|المجموع|amount|total|payment|value"
        for i, line in enumerate(lines):
            if re.search(sender_name_labels, line, re.IGNORECASE) and not result["sender_name"]:
                result["sender_name"] = ReceiptVerifier._label_value(line, sender_name_labels) or (lines[i + 1] if i + 1 < len(lines) else "")
            if re.search(recipient_name_labels, line, re.IGNORECASE) and not result["recipient_name"]:
                result["recipient_name"] = ReceiptVerifier._label_value(line, recipient_name_labels) or (lines[i + 1] if i + 1 < len(lines) else "")
            if re.search(sender_account_labels, line, re.IGNORECASE) and not result["sender_account"]:
                raw = ReceiptVerifier._label_value(line, sender_account_labels) or (lines[i + 1] if i + 1 < len(lines) else "")
                result["sender_account"] = ReceiptVerifier._clean_account(raw)
            if re.search(recipient_account_labels, line, re.IGNORECASE) and not result["recipient_account"]:
                raw = ReceiptVerifier._label_value(line, recipient_account_labels) or (lines[i + 1] if i + 1 < len(lines) else "")
                result["recipient_account"] = ReceiptVerifier._clean_account(raw)
            if re.search(amount_labels, line, re.IGNORECASE) and not result["amount"]:
                amount_match = re.search(r"([\d,]+(?:\.\d+)?)", line)
                if amount_match:
                    result["amount"] = ReceiptVerifier._numeric_value(amount_match.group(1)) or 0.0
        masked = re.findall(r"(\d{3,}\*+|\d{3,}\s*[*xX]+)", text)
        if not result["sender_account"] and masked:
            result["sender_account"] = ReceiptVerifier._clean_account(masked[0])
        if not result["recipient_account"] and len(masked) > 1:
            result["recipient_account"] = ReceiptVerifier._clean_account(masked[1])
        if not result["amount"]:
            currency_match = re.search(r"(?:\$|USDT|USD|SYP|NEW\.SYP|ل\.س|دولار|ليرة|ريال)\s*[:\s]*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
            if currency_match:
                result["amount"] = ReceiptVerifier._numeric_value(currency_match.group(1)) or 0.0
        return result

    @staticmethod
    def _clean_account(value: str) -> str:
        normalized = ReceiptVerifier._normalize_ocr_text(value)
        return re.sub(r"[^0-9*Xx]", "", normalized)

    @staticmethod
    def _label_value(line: str, labels: str) -> str:
        return re.sub(rf"(?:{labels})\s*[:：]?\s*", "", line, flags=re.IGNORECASE).strip(" :-—")

    @staticmethod
    def _date_matches(extracted: str, expected: str) -> bool:
        if not extracted or not expected:
            return False
        normalized = ReceiptVerifier._normalize_ocr_text(extracted).replace("/", "-")
        if normalized == expected:
            return True
        parts = normalized.split("-")
        if len(parts) != 3:
            return False
        if len(parts[0]) == 4:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}" == expected
        return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}" == expected

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
        text = ReceiptVerifier._normalize_ocr_text(text)
        text = re.sub(r"[أإآا]", "ا", text)
        text = re.sub(r"[ةۀ]", "ه", text)
        text = re.sub(r"[ؤ]", "و", text)
        text = re.sub(r"[\u064B-\u065Fـ]", "", text)
        return re.sub(r"\s+", " ", text.strip()).lower()

    @staticmethod
    def _compare_masked_account(extracted: str, expected: str) -> bool:
        if not extracted or not expected:
            return False
        extracted = ReceiptVerifier._normalize_ocr_text(extracted)
        expected = ReceiptVerifier._normalize_ocr_text(expected)
        extracted_digits = re.sub(r"[^0-9]", "", extracted)
        expected_digits = re.sub(r"[^0-9]", "", expected)
        if extracted_digits and expected_digits:
            if extracted_digits == expected_digits:
                return True
            if len(extracted_digits) >= len(expected_digits):
                return False
            prefix_len = min(4, len(extracted_digits), len(expected_digits))
            suffix_len = min(4, len(extracted_digits), len(expected_digits))
            return extracted_digits[:prefix_len] == expected_digits[:prefix_len] or extracted_digits[-suffix_len:] == expected_digits[-suffix_len:]
        extracted_mask = re.sub(r"[^0-9*Xx]", "", extracted).lower()
        expected_digits = re.sub(r"[^0-9]", "", expected)
        if not extracted_mask or not expected_digits:
            return False
        match = re.fullmatch(r"([0-9]{1,})[*x]+([0-9]{0,})", extracted_mask)
        if not match:
            return False
        prefix, suffix = match.groups()
        if prefix and not expected_digits.startswith(prefix):
            return False
        if suffix and not expected_digits.endswith(suffix):
            return False
        return bool(prefix or suffix)
