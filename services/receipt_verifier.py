"""Receipt verification service using OCR."""
import re
import io
import logging
from datetime import datetime

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
            image = Image.open(io.BytesIO(image_bytes))

            text = pytesseract.image_to_string(
                image,
                lang='ara+eng',
                config='--psm 6 --oem 3'
            )

            has_text = bool(text.strip())
            logger.info(f"OCR extracted: {text[:500]}")

            amounts = ReceiptVerifier._extract_amounts(text)

            amount_match = False
            matched_amount = None
            tolerance = expected_amount * 0.02

            for amt in amounts:
                if abs(amt - expected_amount) <= tolerance:
                    amount_match = True
                    matched_amount = amt
                    break

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

        matches = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\b', text)
        for m in matches:
            try:
                val = float(m.replace(',', ''))
                if 0.1 <= val <= 1_000_000:
                    amounts.append(val)
            except ValueError:
                pass

        currency_patterns = re.findall(
            r'(?:USDT|USD|SYP|ل\.س|دولار|ليرة|ريال|₪|د\.ك|\.د\.ب|\.ع\.د|\$)\s*[:\s]*([\d,]+\.?\d*)',
            text, re.IGNORECASE
        )
        for m in currency_patterns:
            try:
                val = float(m.replace(',', ''))
                if 0.1 <= val <= 1_000_000:
                    amounts.append(val)
            except ValueError:
                pass

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

        amounts = sorted(set(round(a, 2) for a in amounts))
        return amounts

    @staticmethod
    async def verify_shamcash_receipt(
        image_bytes: bytes,
        order_date: datetime,
        customer_name: str,
        customer_shamcash_account: str,
        admin_name: str,
        admin_shamcash_account: str,
        expected_amount: float,
        payment_currency: str = 'USD',
    ) -> dict:
        """Verify a ShamCash receipt against all expected data.

        Extracts and compares:
          - Date:  matches order creation date (YYYY-MM-DD)
          - Sender name/account:  matches customer
          - Recipient name/account:  matches admin (SHAMCASH)
          - Amount:  matches order total

        Returns:
            dict with:
                - success: bool
                - text: str — full OCR text
                - fields: dict — extracted values per field
                - matches: dict — per-field match boolean
                - score: int — 0-100 confidence percentage
                - score_label: str — 'عالية' | 'متوسطة' | 'منخفضة' | 'فاشل'
                - summary: str — Arabic human-readable summary
                - details: list[str] — per-field match details in Arabic
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))

            text = pytesseract.image_to_string(
                image,
                lang='ara+eng',
                config='--psm 6 --oem 3'
            )

            logger.info(f"ShamCash OCR text:\n{text[:1000]}")

            extracted = ReceiptVerifier._extract_shamcash_fields(text)
            logger.info(f"Extracted ShamCash fields: {extracted}")

            # ─── Per-field comparison ────────────────────────────────────────
            matches = {}
            details = []

            # 1. Date
            extracted_date = extracted.get('date', '')
            order_date_str = order_date.strftime('%Y-%m-%d') if order_date else ''
            date_match = False
            if extracted_date and order_date_str:
                # Try both YYYY-MM-DD and DD/MM/YYYY
                norm_extracted = extracted_date.replace('/', '-')
                norm_expected = order_date_str
                date_match = norm_extracted == norm_expected
                # Also try reversed (DD-MM-YYYY vs YYYY-MM-DD)
                if not date_match and len(norm_extracted) == 10:
                    parts = norm_extracted.split('-')
                    if len(parts) == 3:
                        rev = f"{parts[2]}-{parts[1]}-{parts[0]}"
                        date_match = rev == norm_expected
            matches['date'] = date_match
            if date_match:
                details.append(f"✅ التاريخ: {extracted_date} ✓ مطابق")
            else:
                details.append(f"❌ التاريخ: {extracted_date or 'غير معروف'} ≠ {order_date_str}")

            # 2. Sender name (customer)
            extracted_sender_name = extracted.get('sender_name', '')
            sender_name_match = False
            if extracted_sender_name and customer_name:
                # Normalize: strip diacritics, extra spaces
                normalized_extracted = ReceiptVerifier._normalize_arabic(extracted_sender_name)
                normalized_expected = ReceiptVerifier._normalize_arabic(customer_name)
                # Check if names overlap significantly
                sender_name_match = (
                    normalized_extracted == normalized_expected
                    or normalized_expected in normalized_extracted
                    or normalized_extracted in normalized_expected
                )
                # Fuzzy: check word overlap
                if not sender_name_match:
                    ext_words = set(normalized_extracted.split())
                    exp_words = set(normalized_expected.split())
                    if len(ext_words) > 0 and len(exp_words) > 0:
                        overlap = ext_words & exp_words
                        ratio = len(overlap) / max(len(ext_words), len(exp_words))
                        sender_name_match = ratio >= 0.5
            matches['sender_name'] = sender_name_match
            if sender_name_match:
                details.append(f"✅ اسم المرسل: {extracted_sender_name} ✓ مطابق")
            else:
                details.append(f"❌ اسم المرسل: {extracted_sender_name or 'غير معروف'} ≠ {customer_name or 'غير مسجل'}")

            # 3. Sender account (customer ShamCash)
            extracted_sender_account = extracted.get('sender_account', '')
            sender_account_match = False
            if extracted_sender_account and customer_shamcash_account:
                # Compare visible digits (accounts may be partially masked)
                sender_account_match = ReceiptVerifier._compare_masked_account(
                    extracted_sender_account, customer_shamcash_account
                )
            matches['sender_account'] = sender_account_match
            if sender_account_match:
                details.append(f"✅ حساب المرسل: {extracted_sender_account} ✓ مطابق")
            else:
                details.append(f"❌ حساب المرسل: {extracted_sender_account or 'غير معروف'} ≠ {customer_shamcash_account or 'غير مسجل'}")

            # 4. Recipient name (admin)
            extracted_recipient_name = extracted.get('recipient_name', '')
            recipient_name_match = False
            if extracted_recipient_name and admin_name:
                normalized_extracted = ReceiptVerifier._normalize_arabic(extracted_recipient_name)
                normalized_expected = ReceiptVerifier._normalize_arabic(admin_name)
                recipient_name_match = (
                    normalized_extracted == normalized_expected
                    or normalized_expected in normalized_extracted
                    or normalized_extracted in normalized_expected
                )
                if not recipient_name_match:
                    ext_words = set(normalized_extracted.split())
                    exp_words = set(normalized_expected.split())
                    if len(ext_words) > 0 and len(exp_words) > 0:
                        overlap = ext_words & exp_words
                        ratio = len(overlap) / max(len(ext_words), len(exp_words))
                        recipient_name_match = ratio >= 0.5
            matches['recipient_name'] = recipient_name_match
            if recipient_name_match:
                details.append(f"✅ اسم المستلم: {extracted_recipient_name} ✓ مطابق")
            else:
                details.append(f"❌ اسم المستلم: {extracted_recipient_name or 'غير معروف'} ≠ {admin_name or 'غير مسجل'}")

            # 5. Recipient account (admin ShamCash)
            extracted_recipient_account = extracted.get('recipient_account', '')
            recipient_account_match = False
            if extracted_recipient_account and admin_shamcash_account:
                recipient_account_match = ReceiptVerifier._compare_masked_account(
                    extracted_recipient_account, admin_shamcash_account
                )
            matches['recipient_account'] = recipient_account_match
            if recipient_account_match:
                details.append(f"✅ حساب المستلم: {extracted_recipient_account} ✓ مطابق")
            else:
                details.append(f"❌ حساب المستلم: {extracted_recipient_account or 'غير معروف'} ≠ {admin_shamcash_account or 'غير مسجل'}")

            # 6. Amount
            extracted_amount = extracted.get('amount', 0)
            amount_match = False
            matched_amount = None
            if extracted_amount > 0 and expected_amount > 0:
                tolerance = expected_amount * 0.02
                amount_match = abs(extracted_amount - expected_amount) <= tolerance
                if amount_match:
                    matched_amount = extracted_amount
            matches['amount'] = amount_match
            if amount_match:
                details.append(f"✅ المبلغ: {extracted_amount:.2f} ✓ مطابق للقيمة المتوقعة {expected_amount:.2f}")
            else:
                details.append(f"❌ المبلغ: {extracted_amount:.2f if extracted_amount else 0:.2f} ≠ {expected_amount:.2f}")

            # ─── Score calculation ──────────────────────────────────────────
            # Weight: date 20%, sender_name 15%, sender_account 15%,
            #         recipient_name 10%, recipient_account 10%, amount 30%
            weights = {
                'date': 20,
                'sender_name': 15,
                'sender_account': 15,
                'recipient_name': 10,
                'recipient_account': 10,
                'amount': 30,
            }
            score = sum(weights[k] for k in weights if matches.get(k))

            # Score label
            if score >= 80:
                score_label = 'عالية'
            elif score >= 50:
                score_label = 'متوسطة'
            elif score > 0:
                score_label = 'منخفضة'
            else:
                score_label = 'فاشل'

            # Overall summary
            matched_fields = sum(1 for v in matches.values() if v)
            total_fields = len(matches)
            summary = (
                f"━━━ 🔍 نتيجة التحقق الآلي من إيصال شام كاش ━━━\n\n"
                f"✅ المطابقة: {matched_fields}/{total_fields} حقلاً\n"
                f"📊 نسبة الثقة: {score}% ({score_label})\n\n"
            )
            summary += "\n".join(details)

            return {
                'success': True,
                'text': text[:1000],
                'fields': extracted,
                'matches': matches,
                'score': score,
                'score_label': score_label,
                'summary': summary,
                'details': details,
                'auto_verified': score >= 80,
                'matched_amount': matched_amount,
            }

        except Exception as e:
            logger.error(f"ShamCash receipt verification failed: {e}")
            return {
                'success': False,
                'text': '',
                'fields': {},
                'matches': {},
                'score': 0,
                'score_label': 'فاشل',
                'summary': f"❌ فشل تحليل الإيصال: {str(e)}",
                'details': [f"❌ خطأ تقني: {str(e)}"],
                'auto_verified': False,
                'matched_amount': None,
            }

    @staticmethod
    def _extract_shamcash_fields(text: str) -> dict:
        """Extract ShamCash-specific fields from OCR text.

        Returns dict with keys:
          - date, sender_name, sender_account, recipient_name,
            recipient_account, amount
        """
        result = {
            'date': '',
            'sender_name': '',
            'sender_account': '',
            'recipient_name': '',
            'recipient_account': '',
            'amount': 0.0,
        }

        # Split into lines for easier processing
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # ─── Date ──────────────────────────────────────────────────────
        # Patterns: YYYY-MM-DD, DD/MM/YYYY, YYYY/MM/DD
        date_patterns = [
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',   # YYYY-MM-DD or YYYY/MM/DD
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',    # DD/MM/YYYY or MM/DD/YYYY
        ]
        for pattern in date_patterns:
            m = re.search(pattern, text)
            if m:
                result['date'] = m.group(1)
                break

        # Also look after "تاريخ العملية" label
        for i, line in enumerate(lines):
            if 'تاريخ' in line or 'التاريخ' in line:
                date_match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', line)
                if date_match:
                    result['date'] = date_match.group(1)
                    break
                # Check next line
                if i + 1 < len(lines):
                    date_match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', lines[i + 1])
                    if date_match:
                        result['date'] = date_match.group(1)
                        break

        # ─── Sender name ───────────────────────────────────────────────
        for i, line in enumerate(lines):
            if 'اسم المرسل' in line or 'Sender' in line:
                # Extract from same line after the label
                name = re.sub(r'اسم المرسل\s*[:：]?\s*', '', line, flags=re.UNICODE).strip()
                name = re.sub(r'Sender\s*[:：]?\s*', '', name, flags=re.IGNORECASE).strip()
                if name and not re.match(r'^[\d\s*]+$', name):
                    result['sender_name'] = name
                    break
                # Try next line
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not re.match(r'^[\d\s*]+$', next_line) and ':' not in next_line:
                        result['sender_name'] = next_line
                        break
        # Fallback: find long Arabic name patterns
        if not result['sender_name']:
            for line in lines:
                # Arabic name: 3+ Arabic words with spaces
                arabic_name = re.findall(r'[\u0600-\u06FF]{2,}(?:\s+[\u0600-\u06FF]{2,}){2,}', line)
                if arabic_name and 'اسم' not in line:
                    result['sender_name'] = arabic_name[0]
                    break

        # ─── Sender account ────────────────────────────────────────────
        for i, line in enumerate(lines):
            if 'حساب المرسل' in line or 'حساب' in line:
                account = re.sub(r'حساب المرسل\s*[:：]?\s*', '', line, flags=re.UNICODE).strip()
                account = re.sub(r'حساب\s*[:：]?\s*', '', account, flags=re.UNICODE).strip()
                # Account is mostly digits and asterisks
                digits = re.sub(r'[^\d*]', '', account)
                if digits:
                    result['sender_account'] = digits
                    break
        # Fallback: find digit+asterisk pattern
        if not result['sender_account']:
            for line in lines:
                masked = re.search(r'(\d{4,}\*+)', line)
                if masked:
                    result['sender_account'] = masked.group(1)
                    break

        # ─── Recipient name ────────────────────────────────────────────
        for i, line in enumerate(lines):
            if 'اسم المستلم' in line or 'المستلم' in line:
                name = re.sub(r'اسم المستلم\s*[:：]?\s*', '', line, flags=re.UNICODE).strip()
                name = re.sub(r'المستلم\s*[:：]?\s*', '', name, flags=re.UNICODE).strip()
                if name and not re.match(r'^[\d\s*]+$', name):
                    result['recipient_name'] = name
                    break
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not re.match(r'^[\d\s*]+$', next_line):
                        result['recipient_name'] = next_line
                        break

        # ─── Recipient account ─────────────────────────────────────────
        for i, line in enumerate(lines):
            if 'حساب المستلم' in line:
                account = re.sub(r'حساب المستلم\s*[:：]?\s*', '', line, flags=re.UNICODE).strip()
                digits = re.sub(r'[^\d*]', '', account)
                if digits:
                    result['recipient_account'] = digits
                    break
        if not result['recipient_account']:
            # Find second masked account (first is sender, second is recipient)
            masked_accounts = re.findall(r'(\d{3,}\*+)', text)
            if len(masked_accounts) >= 2:
                result['recipient_account'] = masked_accounts[1]
            elif len(masked_accounts) == 1:
                # If only one, might be recipient — use as fallback
                if result['sender_account'] and masked_accounts[0] != result['sender_account']:
                    result['recipient_account'] = masked_accounts[0]

        # ─── Amount ────────────────────────────────────────────────────
        for i, line in enumerate(lines):
            if 'المبلغ' in line or 'Amount' in line or 'amount' in line:
                # Look for $ or SYP followed by number
                amt_match = re.search(r'[\$]?\s*([\d,]+\.?\d*)', line)
                if amt_match:
                    try:
                        val = float(amt_match.group(1).replace(',', ''))
                        if val > 0:
                            result['amount'] = val
                            break
                    except ValueError:
                        pass
        if not result['amount']:
            # Fallback: find $XX.XX or XX SYP pattern
            amt_match = re.search(r'\$\s*([\d,]+\.?\d*)', text)
            if amt_match:
                try:
                    result['amount'] = float(amt_match.group(1).replace(',', ''))
                except ValueError:
                    pass

        return result

    @staticmethod
    def _normalize_arabic(text: str) -> str:
        """Normalize Arabic text for comparison."""
        if not text:
            return ''
        text = text.strip()
        # Normalize alef variants
        text = re.sub(r'[أإآا]', 'ا', text)
        # Normalize teh marbouta
        text = re.sub(r'[ةۀ]', 'ه', text)
        # Normalize waw with hamza
        text = re.sub(r'[ؤ]', 'و', text)
        # Remove tashkeel (diacritics)
        text = re.sub(r'[\u064B-\u065F]', '', text)
        # Remove tatweel/kashida
        text = re.sub(r'[ـ]', '', text)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip().lower()

    @staticmethod
    def _compare_masked_account(extracted: str, expected: str) -> bool:
        """Compare a possibly masked account number with the expected one."""
        if not extracted or not expected:
            return False
        # Strip non-digit chars from both
        extracted_digits = re.sub(r'[^\d]', '', extracted)
        expected_digits = re.sub(r'[^\d]', '', expected)

        if not extracted_digits or not expected_digits:
            return False

        # Direct match
        if extracted_digits == expected_digits:
            return True

        # Partial match: check if visible digits match overlapping segments
        # Masked format: 4264******** (partial visible)
        # Compare visible prefix/suffix
        extracted_len = len(extracted_digits)
        expected_len = len(expected_digits)

        if extracted_len < expected_len:
            # extracted is masked (shorter), check prefix/suffix overlap
            prefix_len = min(4, extracted_len, expected_len)
            suffix_len = min(4, extracted_len, expected_len)
            prefix_match = extracted_digits[:prefix_len] == expected_digits[:prefix_len]
            suffix_match = extracted_digits[-suffix_len:] == expected_digits[-suffix_len:]
            return prefix_match or suffix_match

        return False
