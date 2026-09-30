"""Gemini: one multimodal call per message returns transcript, language, translation, category and location
mentions as schema-validated JSON."""

from __future__ import annotations

import logging

from ..taxonomy import SECTOR_DESCRIPTIONS, SECTORS
from .base import Extraction, ExtractionError

PROMPT = """You structure citizen requests for a public-infrastructure planning tool in {country}.
The message may be in any language spoken there (commonly {languages}) or code-mixed, as text or a voice note.
Return JSON matching the schema.
Rules:
- lang is a BCP-47 code; use hi-Latn for Hindi written in Roman script.
- category must be one of: {sectors}. Use "other" if unsure.
- urgency is "high" only for an immediate risk to life, health or safety.
- district_guess is the district, municipality, city or state named in the message, in English, else null.
- Do not invent facts, numbers or places that are not in the message.
- summary_redacted must not contain personal names, phone numbers or house addresses.
Sector guide:
{guide}"""

LANGUAGE_NAMES = {"mr": "Marathi", "hi": "Hindi", "en": "English", "hi-Latn": "Hinglish", "pt": "Portuguese", "ru": "Russian",
                  "zh": "Chinese", "af": "Afrikaans", "zu": "isiZulu", "xh": "isiXhosa"}


log = logging.getLogger(__name__)

# Google retires model versions and has short capacity spikes. These aliases always point at the current Flash and
# Flash-Lite models; Flash-Lite has separate capacity, so it usually answers when Flash is busy.
FALLBACK_MODEL = "gemini-flash-latest"
BACKUP_MODELS = (FALLBACK_MODEL, "gemini-flash-lite-latest")


def _model_gone(exc: Exception) -> bool:
    text = str(exc)
    return "NOT_FOUND" in text or "no longer available" in text or " 404" in text


def _model_busy(exc: Exception) -> bool:
    text = str(exc)
    return any(s in text for s in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "high demand", "overloaded"))


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, country: str, languages: tuple[str, ...] = ()):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30_000))
        self._model = model
        self._prompt = PROMPT.format(
            country=country,
            languages=", ".join(LANGUAGE_NAMES.get(code, code) for code in languages) or "the local languages",
            sectors=", ".join(SECTORS),
            guide="\n".join(f"- {name}: {desc}" for name, desc in SECTOR_DESCRIPTIONS.items()),
        )

    def extract(self, *, text: str | None = None, audio: bytes | None = None, audio_mime: str | None = None) -> Extraction:
        if not (text and text.strip()) and not audio:
            raise ExtractionError("empty message")
        types = self._types
        parts: list = [self._prompt]
        if audio:
            parts.append(types.Part.from_bytes(data=audio, mime_type=(audio_mime or "audio/ogg").split(";")[0]))
        if text:
            parts.append(f"Citizen message:\n{text}")
        try:
            response = self._generate(parts, types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Extraction,
                temperature=0.1,
            ))
            return Extraction.model_validate_json(response.text or "")
        except Exception as exc:  # network, quota, safety block or schema mismatch: all go to review
            raise ExtractionError(f"gemini extraction failed: {exc}") from exc

    def write(self, prompt: str, *, max_tokens: int = 700) -> str:
        """Free text for the assist features (briefs). Raises ExtractionError so callers can fall back."""
        try:
            response = self._generate([prompt], self._types.GenerateContentConfig(temperature=0.3, max_output_tokens=max_tokens))
        except Exception as exc:
            raise ExtractionError(f"gemini generation failed: {exc}") from exc
        text = (response.text or "").strip()
        if not text:
            raise ExtractionError("gemini returned no text")
        return text

    def _generate(self, contents: list, config):
        """Call the configured model. A retired model is replaced by the current Flash alias for good; a busy or
        rate-limited one is skipped for this call only, trying the backups in order."""
        candidates = [self._model, *[m for m in BACKUP_MODELS if m != self._model]]
        last: Exception | None = None
        for model in candidates:
            try:
                return self._client.models.generate_content(model=model, contents=contents, config=config)
            except Exception as exc:
                last = exc
                if _model_gone(exc):
                    if model == self._model and model not in BACKUP_MODELS:
                        log.warning("Gemini model %r is no longer available; using %r from now on. Set GEMINI_MODEL "
                                    "to silence this.", model, FALLBACK_MODEL)
                        self._model = FALLBACK_MODEL
                    continue
                if _model_busy(exc):
                    log.warning("Gemini model %r is busy (%s); trying the next one", model, str(exc)[:80])
                    continue
                raise
        raise last  # type: ignore[misc]
