from __future__ import annotations

from ..config import Settings
from .base import Extraction, ExtractionError, LanguageProvider
from .offline import OfflineProvider

__all__ = ["Extraction", "ExtractionError", "LanguageProvider", "OfflineProvider", "build_provider"]


def build_provider(settings: Settings, region: str) -> LanguageProvider:
    if settings.language_provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("LANGUAGE_PROVIDER=gemini but GEMINI_API_KEY is not set")
        from .gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key, settings.gemini_model, region)
    if settings.language_provider == "offline":
        return OfflineProvider()
    raise RuntimeError(f"unknown LANGUAGE_PROVIDER {settings.language_provider!r}")
