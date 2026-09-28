"""Gemini: one multimodal call per message returns transcript, language, translation, category and location
mentions as schema-validated JSON."""

from __future__ import annotations

from ..taxonomy import SECTOR_DESCRIPTIONS, SECTORS
from .base import Extraction, ExtractionError

PROMPT = """You structure citizen requests for a public-infrastructure planning tool in {region}, India.
The message may be Marathi, Hindi, English, or code-mixed (e.g. Hinglish in Roman script), as text or a voice note.
Return JSON matching the schema.
Rules:
- category must be one of: {sectors}. Use "other" if unsure.
- urgency is "high" only for an immediate risk to life, health or safety.
- Do not invent facts, numbers or places that are not in the message.
- summary_redacted must not contain personal names, phone numbers or house addresses.
Sector guide:
{guide}"""


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, region: str):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30_000))
        self._model = model
        self._prompt = PROMPT.format(
            region=region,
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
