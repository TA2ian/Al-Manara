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


# Singleton
locale_service = LocaleService()
