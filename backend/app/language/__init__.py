from __future__ import annotations

import logging

from ..config import Settings
from .base import Extraction, ExtractionError, LanguageProvider
from .offline import OfflineProvider

__all__ = ["Extraction", "ExtractionError", "LanguageProvider", "OfflineProvider", "build_provider"]

log = logging.getLogger(__name__)


def build_provider(settings: Settings, country: str, languages: tuple[str, ...] = ()) -> LanguageProvider:
    if settings.language_provider == "gemini":
        if not settings.gemini_api_key:
            # Keep the app usable (typed complaints still work) rather than failing every request.
            log.warning("LANGUAGE_PROVIDER=gemini but GEMINI_API_KEY is not set: using the offline provider "
                        "(no translation, no voice notes). Set GEMINI_API_KEY in .env to enable Gemini.")
            return OfflineProvider(languages)
        from .gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key, settings.gemini_model, country, languages)
    if settings.language_provider == "offline":
        return OfflineProvider(languages)
    raise RuntimeError(f"unknown LANGUAGE_PROVIDER {settings.language_provider!r}")
