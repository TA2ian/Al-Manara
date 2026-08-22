"""ShamCash QR/account matching helpers.

The customer-entered ShamCash receiving identifier must match the identifier
encoded by the submitted QR before verification is sent to an administrator.
The existing verification flow remains responsible for storing the photo and
submitting the verification request; this module only performs the safety
check.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse


_PREFIXES = ("shamcash:", "shamcash://", "pay:", "account:", "address:", "recipient:")
_QUERY_KEYS = ("account", "address", "recipient", "receiver", "phone", "username", "id")


def normalize_shamcash_value(value: str) -> str:
    """Normalize harmless formatting differences without changing identity."""
    value = unquote((value or "").strip()).strip("\u200b\ufeff")
    value = re.sub(r"\s+", "", value)
    return value.casefold()


def _candidates(qr_text: str) -> set[str]:
    raw = (qr_text or "").strip()
    if not raw:
        return set()

    candidates = {normalize_shamcash_value(raw)}
    lowered = raw.casefold()

    for prefix in _PREFIXES:
        if lowered.startswith(prefix):
            candidates.add(normalize_shamcash_value(raw[len(prefix):]))

    parsed = urlparse(raw)
    if parsed.query:
        query = parse_qs(parsed.query)
        for key in _QUERY_KEYS:
            for value in query.get(key, []):
                candidates.add(normalize_shamcash_value(value))
    if parsed.path and parsed.scheme:
        candidates.add(normalize_shamcash_value(parsed.path.strip("/")))

    return {item for item in candidates if item}


def qr_matches_account(account: str, qr_text: str) -> bool:
    """Return True only when the entered account matches QR data."""
    normalized_account = normalize_shamcash_value(account)
    if not normalized_account:
        return False
    return normalized_account in _candidates(qr_text)
