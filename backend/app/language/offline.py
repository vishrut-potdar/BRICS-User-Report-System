"""Keyword stub so the pipeline runs with no API key (dev, tests, CI).

It does not translate or transcribe: text_en is marked untranslated and audio is rejected. Never demo with it.
"""

from __future__ import annotations

import re

from ..privacy import redact
from .base import Extraction, ExtractionError

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_CJK = re.compile(r"[一-鿿]")
_MARATHI_MARKERS = ("आहे", "नाही", "आमच्या", "आमचे", "मध्ये", "ळ", "च्या", "येत")
_LATIN_MARKERS = {  # function words that are frequent in one language and rare in the others
    "pt": frozenset("não nao está esta nossa nosso nós temos há faz uma para com rua bairro água agua dias na da perto muito sem".split()),
    "af": frozenset("ons nie het geen ook dae straat asseblief kraan krag reën".split()),
    "zu": frozenset("akukho sicela yethu kwethu amanzi ugesi isikole umgwaqo izinsuku kule".split()),
    "xh": frozenset("akukho sicela yethu kweli amanzi umbane isikolo indlela iintsuku kule".split()),
}
_HINGLISH_MARKERS = frozenset(
    "hai nahi nahin mein ka ki ke se raha rahi rahe hamare hamara aap kar ho gaya gayi bhi ko pe par".split()
)

SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "water": ("water", "tap", "handpump", "hand pump", "tanker", "borewell", "paani", "pani", "nal",
              "पानी", "पाणी", "नळ", "नल", "हैंडपंप", "टँकर", "टैंकर", "बोअरवेल",
              "agua", "água", "torneira", "poço", "caminhão-pipa", "abastecimento",  # pt
              "вода", "воды", "водопровод", "колодец", "скважина",  # ru
              "水", "自来水", "饮水", "水管", "井",  # zh
              "kraan", "amanzi", "manzi", "impompi", "umthombo"),  # af, zu/xh
    "sanitation": ("toilet", "drain", "sewage", "sewer", "gutter", "nala", "shauchalay",
                   "शौचालय", "गटार", "नाली", "सीवर", "सांडपाणी", "स्वच्छतागृह",
                   "esgoto", "banheiro", "fossa", "bueiro",
                   "канализация", "канализации", "туалет", "стоки",
                   "厕所", "下水道", "污水", "排水",
                   "riool", "toilette", "indlu yangasese", "ithoyilethi", "amanzi angcolileyo"),
    "roads": ("road", "pothole", "potholes", "bridge", "sadak", "gaddhe", "gaddha",
              "सड़क", "सडक", "रस्ता", "खड्डे", "गड्ढे", "पूल", "पुल",
              "estrada", "rua", "buraco", "buracos", "asfalto", "ponte", "calçamento",
              "дорога", "дороги", "дорогу", "яма", "ямы", "мост", "асфальт",
              "路", "道路", "坑", "桥", "公路",
              "pad", "slaggat", "slaggate", "brug", "umgwaqo", "indlela", "ibhuloho"),
    "health": ("hospital", "doctor", "clinic", "medicine", "ambulance", "phc", "dawai", "dawakhana",
               "अस्पताल", "डॉक्टर", "दवा", "दवाखाना", "रुग्णालय", "आरोग्य", "स्वास्थ्य", "एम्बुलेंस", "रुग्णवाहिका",
               "posto de saúde", "posto de saude", "médico", "medico", "remédio", "remedio", "ambulância", "ubs",
               "больница", "поликлиника", "врач", "фап", "лекарства", "скорая",
               "医院", "卫生院", "诊所", "医生", "药", "救护车",
               "kliniek", "hospitaal", "dokter", "ikliniki", "umtholampilo", "isibhedlela", "udokotela", "ugqirha"),
    "education": ("school", "teacher", "classroom", "shala", "स्कूल", "शाळा", "शिक्षक", "विद्यालय",
                  "escola", "professor", "professora", "creche",
                  "школа", "школе", "школы", "учитель", "детский сад",
                  "学校", "老师", "教室", "小学",
                  "skool", "onderwyser", "isikole", "isikolo", "uthisha", "utitshala"),
    "electricity": ("electricity", "power", "light", "transformer", "bijli", "streetlight", "street light",
                    "बिजली", "वीज", "ट्रांसफार्मर", "लाइट", "लाईट",
                    "luz", "energia", "iluminação", "poste", "transformador",
                    "свет", "электричество", "электроэнергия", "фонари", "трансформатор",
                    "电", "停电", "路灯", "电力",
                    "krag", "elektrisiteit", "beurtkrag", "loadshedding", "load shedding", "ugesi", "gesi", "umbane", "mbane"),
    "waste": ("garbage", "waste", "trash", "kachra", "dump", "कचरा", "कचऱ्या", "घंटागाडी",
              "lixo", "coleta", "entulho",
              "мусор", "свалка", "отходы",
              "垃圾",
              "vullis", "rommel", "udoti", "inkunkuma"),
}
URGENT_KEYWORDS = ("ambulance", "accident", "emergency", "unsafe", "danger", "collapsed", "shock", "beemar",
                   "बीमार", "खतरा", "धोका", "दुर्घटना", "अपघात", "आजारी", "करंट",
                   "perigo", "acidente", "urgente", "doentes", "doente",
                   "опасно", "авария", "срочно", "болеют",
                   "危险", "事故", "紧急", "生病",
                   "gevaar", "ongeluk", "dringend", "ingozi", "siyagula", "bayagula")


def _compile(words: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [
        re.compile(rf"(?<![a-z]){re.escape(w)}(?![a-z])") if w.isascii() else re.compile(re.escape(w))
        for w in words
    ]


_SECTOR_PATTERNS = {sector: _compile(words) for sector, words in SECTOR_KEYWORDS.items()}
_URGENT_PATTERNS = _compile(URGENT_KEYWORDS)


def detect_lang(text: str, allowed: tuple[str, ...] = ()) -> str:
    """Best guess from script and marker words. With `allowed` (the country's languages), the answer is always one
    of them: an Indian complaint is never read as Afrikaans."""
    lang = _guess_lang(text)
    if not allowed or lang in allowed:
        return lang
    if lang in ("hi", "mr") and ({"hi", "mr"} & set(allowed)):
        return "hi" if "hi" in allowed else "mr"
    latin = [a for a in allowed if a in ("en", "hi-Latn", "pt", "af", "zu", "xh")]
    if text.isascii() or lang in _LATIN_MARKERS or lang == "en":
        return "en" if "en" in allowed else (latin[0] if latin else allowed[0])
    return allowed[0]


def _guess_lang(text: str) -> str:
    if _CJK.search(text):
        return "zh"
    if _CYRILLIC.search(text):
        return "ru"
    if _DEVANAGARI.search(text):
        return "mr" if any(marker in text for marker in _MARATHI_MARKERS) else "hi"
    tokens = set(re.findall(r"[a-zà-ÿ]+", text.casefold()))
    if len(tokens & _HINGLISH_MARKERS) >= 2:
        return "hi-Latn"
    scores = {lang: len(tokens & markers) for lang, markers in _LATIN_MARKERS.items()}
    best = max(scores, key=lambda lang: scores[lang])
    if scores[best] >= 2 or any(c in text for c in "ãõç"):
        if best in ("zu", "xh") and scores["zu"] == scores["xh"]:
            return "xh" if re.search(r"(umbane|isikolo|kweli|iintsuku)", text.casefold()) else "zu"
        return best if scores[best] else "pt"
    return "en"


def classify(text: str) -> str:
    folded = text.casefold()
    hits = {sector: sum(bool(p.search(folded)) for p in patterns) for sector, patterns in _SECTOR_PATTERNS.items()}
    best = max(hits, key=lambda s: hits[s])  # ties go to the earlier sector in SECTOR_KEYWORDS
    return best if hits[best] else "other"


class OfflineProvider:
    name = "offline"

    def __init__(self, languages: tuple[str, ...] = ()):
        self._languages = tuple(languages)

    def extract(self, *, text: str | None = None, audio: bytes | None = None, audio_mime: str | None = None) -> Extraction:
        if not text or not text.strip():
            raise ExtractionError("offline provider needs text (it cannot transcribe audio); set GEMINI_API_KEY")
        lang = detect_lang(text, self._languages)
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
