"""Geo-resolution cascade: device GPS or a pin → geocoded place (Google or OpenStreetMap) → gazetteer → unresolved.

Confidence tiers: A = GPS pin, B = geocoded to locality or finer, C = district only.
Only A and B get an H3 cell; C still counts at district level.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from typing import Sequence

import h3

from .geocode import Geocoder, GeocodeHit
from .models import Geo
from .pack import PackContext, Polygon, Ring

log = logging.getLogger(__name__)

MAX_CENTROID_KM = 120.0


def _in_ring(lon: float, lat: float, ring: Ring) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _in_polygon(lon: float, lat: float, polygon: Polygon) -> bool:
    return bool(polygon) and _in_ring(lon, lat, polygon[0]) and not any(_in_ring(lon, lat, h) for h in polygon[1:])


def _fold(text: str) -> str:
    """Casefold and drop accents on Latin letters, so "Maceio" matches "Maceió" and "Sao Paulo" matches "São Paulo".
    Marks on other scripts (Devanagari vowel signs, for instance) are kept."""
    out, latin_base = [], False
    for ch in unicodedata.normalize("NFKD", text.casefold()):
        if unicodedata.combining(ch):
            if latin_base:
                continue
        else:
            latin_base = ch.isascii()
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


class GeoResolver:
    def __init__(self, ctx: PackContext, geocoder: Geocoder | None = None):
        self._ctx = ctx
        self._geocoder = geocoder
        self._aliases = self._compile((a, code) for code, info in ctx.info.items() for a in info.aliases)
        self._weak = self._compile((a, code) for code, info in ctx.info.items() for a in info.weak_aliases)

    @staticmethod
    def _compile(pairs) -> list[tuple[str, re.Pattern[str] | None, str]]:
        aliases = []
        for alias, code in pairs:
            folded = _fold(alias)
            # Latin names need word boundaries ("Beed" must not match "breed"). Other scripts are matched as
            # substrings: Chinese has no spaces, and Russian and Marathi inflect place names ("в Кызыле").
            pattern = re.compile(rf"(?<![a-z]){re.escape(folded)}(?![a-z])") if folded.isascii() else None
            aliases.append((folded, pattern, code))
        return sorted(aliases, key=lambda a: -len(a[0]))  # longest match wins: "Mumbai Suburban" > "Mumbai"

    def district_for_point(self, lat: float, lon: float) -> str | None:
        if self._ctx.boundaries:
            for code, polygons in self._ctx.boundaries.items():
                if any(_in_polygon(lon, lat, p) for p in polygons):
                    return code
            return None
        # No boundaries file yet: nearest district centroid. Approximate near district borders.
        best = min(self._ctx.info.values(), key=lambda i: _km(lat, lon, i.lat, i.lon), default=None)
        if best is None or _km(lat, lon, best.lat, best.lon) > MAX_CENTROID_KM:
            return None
        return best.admin_code

    def match_gazetteer(self, texts: Sequence[str], *, allow_weak: bool = False) -> str | None:
        """First alias found. Weak aliases ("Pilar", "North West") are only tried when the texts are place
        mentions or a district guess, never a free-text transcript."""
        tables = [self._aliases, self._weak] if allow_weak else [self._aliases]
        for text in texts:
            folded = _fold(text or "")
            if not folded:
                continue
            for table in tables:
                for alias, pattern, code in table:
                    if (pattern.search(folded) if pattern else alias in folded):
                        return code
        return None

    def geocode(self, query: str, hint: Sequence[str] = ()) -> GeocodeHit | None:
        """Search a typed place inside this pack's country (and state, for a pilot region)."""
        if not self._geocoder or not self._geocoder.enabled:
            return None
        region = self._ctx.region_name if self._ctx.level == "region" else None
        full = ", ".join(dict.fromkeys(part for part in (query, *hint) if part and part != region))
        return self._geocoder.geocode(full, self._ctx.country, region)

    def _point_geo(self, lat: float, lon: float, *, confidence: str, method: str, location_text: str | None) -> Geo:
        code = self.district_for_point(lat, lon)
        return Geo(
            lat=lat,
            lon=lon,
            h3=h3.latlng_to_cell(lat, lon, self._ctx.h3_resolution),
            admin_code=code,
            district=self._ctx.info[code].name if code else None,
            location_text=location_text,
            confidence=confidence,
            method=method,
        )

    def resolve(
        self,
        *,
        lat: float | None = None,
        lon: float | None = None,
        mentions: Sequence[str] = (),
        district_guess: str | None = None,
        transcript: str = "",
        typed_location: str | None = None,
        hint: Sequence[str] = (),
        point_confidence: str = "A",
    ) -> Geo:
        """`typed_location` is what the citizen wrote in the location box; `hint` names the area they picked, to
        narrow the search. `point_confidence` is A for device GPS, B for a pin they placed or a searched place."""
        mentions = [m for m in mentions if m and m.strip()]
        typed = (typed_location or "").strip()
        location_text = "; ".join(dict.fromkeys([typed, *mentions] if typed else mentions)) or None
        if lat is not None and lon is not None:
            method = "gps" if point_confidence == "A" else "pin"
            return self._point_geo(lat, lon, confidence=point_confidence, method=method, location_text=location_text)

        gazetteer_code = (self.match_gazetteer([typed, district_guess or "", *mentions], allow_weak=True)
                          or self.match_gazetteer([transcript]))
        queries = ([typed] if typed else []) + ([", ".join(mentions)] if mentions else [])
        for query in queries:
            area = [self._ctx.info[gazetteer_code].name] if gazetteer_code else []
            hit = self.geocode(query, [*area, *hint])
            if hit and hit.precise:
                geo = self._point_geo(hit.lat, hit.lon, confidence="B", method="geocode", location_text=location_text)
                if geo.admin_code and (gazetteer_code is None or geo.admin_code == gazetteer_code):
                    return geo

        if gazetteer_code:
            info = self._ctx.info[gazetteer_code]
            return Geo(admin_code=gazetteer_code, district=info.name, location_text=location_text, confidence="C", method="gazetteer")
        return Geo(location_text=location_text, confidence="C", method="none")
