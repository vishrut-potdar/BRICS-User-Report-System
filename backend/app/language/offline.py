"""Keyword stub so the pipeline runs with no API key (dev, tests, CI).

It does not translate or transcribe: text_en is marked untranslated and audio is rejected. Never demo with it.
"""

from __future__ import annotations

import re

from ..privacy import redact
from .base import Extraction, ExtractionError

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_MARATHI_MARKERS = ("आहे", "नाही", "आमच्या", "आमचे", "मध्ये", "ळ", "च्या", "येत")
_HINGLISH_MARKERS = frozenset(
    "hai nahi nahin mein ka ki ke se raha rahi rahe hamare hamara aap kar ho gaya gayi bhi ko pe par".split()
)

SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "water": ("water", "tap", "handpump", "hand pump", "tanker", "borewell", "paani", "pani", "nal",
              "पानी", "पाणी", "नळ", "नल", "हैंडपंप", "टँकर", "टैंकर", "बोअरवेल"),
    "sanitation": ("toilet", "drain", "sewage", "sewer", "gutter", "nala", "shauchalay",
                   "शौचालय", "गटार", "नाली", "सीवर", "सांडपाणी", "स्वच्छतागृह"),
    "roads": ("road", "pothole", "potholes", "bridge", "sadak", "gaddhe", "gaddha",
              "सड़क", "सडक", "रस्ता", "खड्डे", "गड्ढे", "पूल", "पुल"),
    "health": ("hospital", "doctor", "clinic", "medicine", "ambulance", "phc", "dawai", "dawakhana",
               "अस्पताल", "डॉक्टर", "दवा", "दवाखाना", "रुग्णालय", "आरोग्य", "स्वास्थ्य", "एम्बुलेंस", "रुग्णवाहिका"),
    "education": ("school", "teacher", "classroom", "shala", "स्कूल", "शाळा", "शिक्षक", "विद्यालय"),
    "electricity": ("electricity", "power", "light", "transformer", "bijli", "streetlight", "street light",
                    "बिजली", "वीज", "ट्रांसफार्मर", "लाइट", "लाईट"),
    "waste": ("garbage", "waste", "trash", "kachra", "dump", "कचरा", "कचऱ्या", "घंटागाडी"),
}
URGENT_KEYWORDS = ("ambulance", "accident", "emergency", "unsafe", "danger", "collapsed", "shock", "beemar",
                   "बीमार", "खतरा", "धोका", "दुर्घटना", "अपघात", "आजारी", "करंट")


def _compile(words: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [
        re.compile(rf"(?<![a-z]){re.escape(w)}(?![a-z])") if w.isascii() else re.compile(re.escape(w))
        for w in words
    ]


_SECTOR_PATTERNS = {sector: _compile(words) for sector, words in SECTOR_KEYWORDS.items()}
_URGENT_PATTERNS = _compile(URGENT_KEYWORDS)


def detect_lang(text: str) -> str:
    if _DEVANAGARI.search(text):
        return "mr" if any(marker in text for marker in _MARATHI_MARKERS) else "hi"
    tokens = set(re.findall(r"[a-z]+", text.casefold()))
    return "hi-Latn" if len(tokens & _HINGLISH_MARKERS) >= 2 else "en"


def classify(text: str) -> str:
    folded = text.casefold()
    hits = {sector: sum(bool(p.search(folded)) for p in patterns) for sector, patterns in _SECTOR_PATTERNS.items()}
    best = max(hits, key=lambda s: hits[s])  # ties go to the earlier sector in SECTOR_KEYWORDS
    return best if hits[best] else "other"


class OfflineProvider:
    name = "offline"

    def extract(self, *, text: str | None = None, audio: bytes | None = None, audio_mime: str | None = None) -> Extraction:
        if not text or not text.strip():
            raise ExtractionError("offline provider needs text (it cannot transcribe audio); set GEMINI_API_KEY")
        lang = detect_lang(text)
        folded = text.casefold()
        urgent = any(p.search(folded) for p in _URGENT_PATTERNS)
        return Extraction(
            lang=lang,
            code_mixed=lang == "hi-Latn",
            transcript=text,
            text_en=text if lang == "en" else f"[untranslated: offline provider] {text}",
            category=classify(text),
            sub_type="",
            urgency="high" if urgent else "medium",
            location_mentions=[],
            district_guess=None,
            summary_redacted=redact(text)[:280],
        )
