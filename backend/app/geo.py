"""Geo-resolution cascade: device GPS → geocoded landmark (Google Maps) → district-name gazetteer → unresolved.

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
import httpx

from .models import Geo
from .pack import PackContext, Polygon, Ring

log = logging.getLogger(__name__)

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PRECISE_TYPES = frozenset(
    {"street_address", "premise", "route", "point_of_interest", "establishment", "neighborhood",
     "sublocality", "sublocality_level_1", "sublocality_level_2", "locality"}
)
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
    def __init__(self, ctx: PackContext, maps_api_key: str | None = None, http: httpx.Client | None = None):
        self._ctx = ctx
        self._maps_key = maps_api_key
        self._http = http or httpx.Client(timeout=10.0)
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

    def _geocode(self, query: str) -> tuple[float, float, bool] | None:
        params = {
            "address": query,
            "components": f"country:{self._ctx.country}"
            + (f"|administrative_area:{self._ctx.region_name}" if self._ctx.level == "region" else ""),
            "key": self._maps_key,
        }
        try:
            response = self._http.get(GEOCODE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("geocoding failed: %s", exc)
            return None
        if data.get("status") != "OK" or not data.get("results"):
            return None
        top = data["results"][0]
        location = top["geometry"]["location"]
        precise = bool(PRECISE_TYPES & set(top.get("types", [])))
        return float(location["lat"]), float(location["lng"]), precise

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
    ) -> Geo:
        mentions = [m for m in mentions if m and m.strip()]
        location_text = "; ".join(mentions) or None
        if lat is not None and lon is not None:
            return self._point_geo(lat, lon, confidence="A", method="gps", location_text=location_text)

        gazetteer_code = self.match_gazetteer([district_guess or "", *mentions], allow_weak=True) or self.match_gazetteer([transcript])
        if self._maps_key and mentions:
            query = ", ".join(mentions + ([self._ctx.info[gazetteer_code].name] if gazetteer_code else []))
            hit = self._geocode(query)
            if hit and hit[2]:
                geo = self._point_geo(hit[0], hit[1], confidence="B", method="geocode", location_text=location_text)
                if geo.admin_code and (gazetteer_code is None or geo.admin_code == gazetteer_code):
                    return geo

        if gazetteer_code:
            info = self._ctx.info[gazetteer_code]
            return Geo(admin_code=gazetteer_code, district=info.name, location_text=location_text, confidence="C", method="gazetteer")
        return Geo(location_text=location_text, confidence="C", method="none")
