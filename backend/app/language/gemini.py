"""Gemini: one multimodal call per message returns transcript, language, translation, category and location
mentions as schema-validated JSON."""

from __future__ import annotations

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
            response = self._client.models.generate_content(
                model=self._model,
                contents=parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Extraction,
                    temperature=0.1,
                ),
            )
            return Extraction.model_validate_json(response.text or "")
        except Exception as exc:  # network, quota, safety block or schema mismatch: all go to review
            raise ExtractionError(f"gemini extraction failed: {exc}") from exc
