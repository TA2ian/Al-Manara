"""Receipt verification service using OCR."""
import re
import io
import logging
import tempfile
import os

from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)


class ReceiptVerifier:
    """Verify payment receipts using OCR."""

    @staticmethod
    async def analyze_receipt(image_bytes: bytes, expected_amount: float) -> dict:
        """Analyze receipt image and verify against expected amount.

        Returns:
            dict with:
                - success: bool — whether analysis ran
                - text: str — extracted text
                - extracted_amounts: list[float] — amounts found in image
                - amount_match: bool — whether an amount close to expected was found
                - has_text: bool — whether any text was detected
                - confidence: str — 'high', 'medium', 'low', or 'none'
                - message: str — human-readable result
        """
        try:
            # Open and preprocess the image
            image = Image.open(io.BytesIO(image_bytes))

            # Run OCR with Arabic + English
            text = pytesseract.image_to_string(
                image,
                lang='ara+eng',
                config='--psm 6 --oem 3'
            )

            has_text = bool(text.strip())
            logger.info(f"OCR extracted: {text[:500]}")

            # Find all numbers that look like currency amounts
            amounts = ReceiptVerifier._extract_amounts(text)

            # Check if any extracted amount matches the expected total
            amount_match = False
            matched_amount = None
            tolerance = expected_amount * 0.02  # 2% tolerance

            for amt in amounts:
                if abs(amt - expected_amount) <= tolerance:
                    amount_match = True
                    matched_amount = amt
                    break

            # Determine confidence
            if amount_match and has_text:
                confidence = 'high'
                message = f"✅ تم التحقق آلياً: المبلغ {matched_amount:.2f} مطابق للقيمة المتوقعة {expected_amount:.2f}"
            elif has_text and amounts:
                confidence = 'medium'
                nearest = min(amounts, key=lambda x: abs(x - expected_amount))
                message = (
                    f"⚠️ تطابق جزئي: تم العثور على مبالغ ({', '.join(f'{a:.2f}' for a in amounts[:5])}) "
                    f"لكن لا تطابق القيمة المتوقعة {expected_amount:.2f} (الأقرب: {nearest:.2f})"
                )
            elif has_text:
                confidence = 'low'
                message = "⚠️ تم العثور على نص في الصورة لكن لم يتم التعرف على مبالغ محددة"
            else:
                confidence = 'none'
                message = "❌ لم يتم التعرف على أي نص في الصورة. قد لا تكون صورة إيصال صالحة."

            return {
                'success': True,
                'text': text[:1000],
                'extracted_amounts': amounts,
                'amount_match': amount_match,
                'has_text': has_text,
                'confidence': confidence,
                'message': message,
                'matched_amount': matched_amount,
            }

        except Exception as e:
            logger.error(f"Receipt analysis failed: {e}")
            return {
                'success': False,
                'text': '',
                'extracted_amounts': [],
                'amount_match': False,
                'has_text': False,
                'confidence': 'error',
                'message': f"❌ فشل تحليل الصورة: {str(e)}",
                'matched_amount': None,
            }

    @staticmethod
    def _extract_amounts(text: str) -> list[float]:
        """Extract currency amounts from OCR text."""
        amounts = []

        # Pattern 1: Numbers with decimal points (e.g., 15000.00, 10.50)
        matches = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\b', text)
        for m in matches:
            try:
                val = float(m.replace(',', ''))
                # Filter out very small and very large amounts
                if 0.1 <= val <= 1_000_000:
                    amounts.append(val)
            except ValueError:
                pass

        # Pattern 2: Arabic/English currency prefixes
        currency_patterns = re.findall(
            r'(?:USDT|USD|SYP|ل\.س|دولار|ليرة|ريال|₪|د\.ك|\.د\.ب|\.ع\.د)\s*[:\s]*([\d,]+\.?\d*)',
            text, re.IGNORECASE
        )
        for m in currency_patterns:
            try:
                val = float(m.replace(',', ''))
                if 0.1 <= val <= 1_000_000:
                    amounts.append(val)
            except ValueError:
                pass

        # Pattern 3: Total/sum keywords nearby numbers
        total_keywords = r'(?:المجموع|الإجمالي|المبلغ|total|amount|مجموع|payment|قيمة|TOTAL|Amount)'
        total_matches = re.findall(
            rf'{total_keywords}[^\d]*([\d,]+\.?\d*)',
            text, re.IGNORECASE
        )
        for m in total_matches:
            try:
                val = float(m.replace(',', ''))
                if 0.1 <= val <= 1_000_000:
                    amounts.append(val)
            except ValueError:
                pass

        # Remove duplicates and sort
        amounts = sorted(set(round(a, 2) for a in amounts))

        return amounts
