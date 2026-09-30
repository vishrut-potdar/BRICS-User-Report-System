"""Language-provider interface. Gemini is the default; any provider returning an Extraction can replace it
(e.g. Bhashini/IndicConformer ASR + IndicTrans2 + a classifier), which keeps the platform vendor-independent."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from ..taxonomy import Sector


class Extraction(BaseModel):
    """Structured reading of one citizen message. The provider classifies; it never scores."""

    lang: str = Field(description="BCP-47 code, e.g. mr, hi, en, pt, ru, zh, af, zu, xh; hi-Latn for Hindi in Roman script")
    code_mixed: bool = Field(description="True if the message mixes languages, e.g. Hinglish")
    transcript: str = Field(description="Verbatim transcript of the audio, or the original text")
    text_en: str = Field(description="Faithful English translation")
    category: Sector
    sub_type: str = Field(description="Short snake_case sub-type, e.g. handpump_broken")
    urgency: Literal["low", "medium", "high"] = Field(description="high only for an immediate risk to life, health or safety")
    location_mentions: list[str] = Field(description="Place names and landmarks mentioned, as written")
    district_guess: str | None = Field(default=None, description="District, municipality, city or state named, in English, else null")
    summary_redacted: str = Field(description="One English sentence; no personal names, phone numbers or house addresses")


class ExtractionError(RuntimeError):
    """The provider could not structure the message; the request goes to the review queue."""


class LanguageProvider(Protocol):
    name: str

    def extract(self, *, text: str | None = None, audio: bytes | None = None, audio_mime: str | None = None) -> Extraction: ...
