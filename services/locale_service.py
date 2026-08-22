"""Localization service."""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LocaleService:
    """Service for managing translations."""

    def __init__(self):
        self._locales: Dict[str, Dict[str, str]] = {}
        self._load_locales()

    def _load_locales(self):
        """Load locale files."""
        for lang in ['ar', 'en']:
            try:
                with open(f'locales/{lang}.json', 'r', encoding='utf-8') as f:
                    self._locales[lang] = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load locale {lang}: {e}")
                self._locales[lang] = {}

        if 'ar' in self._locales:
            self._locales['ar']['enter_amount'] = "💵 اختر كمية USDT التي تريد شراءها:"
            self._locales['ar']['enter_amount_custom'] = "💵 أدخل كمية USDT التي تريد شراءها:\n\nالحد الأدنى: {min} USDT\nالحد الأقصى: {max} USDT\n\nمثال صحيح: 100"
            self._locales['ar']['invalid_amount'] = "❌ كمية غير صحيحة.\n\nالحد الأدنى: {min} USDT\nالحد الأقصى: {max} USDT"
        if 'en' in self._locales:
            self._locales['en']['enter_amount'] = "💵 Choose the amount of USDT you want to buy:"
            self._locales['en']['enter_amount_custom'] = "💵 Enter the amount of USDT you want to buy:\n\nMinimum: {min} USDT\nMaximum: {max} USDT\n\nExample: 100"
            self._locales['en']['invalid_amount'] = "❌ Invalid USDT amount.\n\nMinimum: {min} USDT\nMaximum: {max} USDT"

    def get(self, key: str, lang: str = 'ar', **kwargs) -> str:
        """Get translated string."""
        text = self._locales.get(lang, {}).get(key, key)

        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing format key {e} for '{key}'")

        return text

    def get_language_name(self, lang: str) -> str:
        """Get language display name."""
        names = {'ar': 'العربية', 'en': 'English'}
        return names.get(lang, lang)


locale_service = LocaleService()
