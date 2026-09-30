"""Place search: Google Geocoding when a key is set, else OpenStreetMap Nominatim (free, no key).

Nominatim's usage policy asks for at most one request per second and an identifying User-Agent; both are honoured,
and results are cached. For production volume, run your own Nominatim or use Google.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

GOOGLE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "VikasVaani/0.2 (civic demand prototype; https://github.com/vishrut-potdar/BRICS-User-Report-System)"
GOOGLE_PRECISE = frozenset(
    {"street_address", "premise", "route", "point_of_interest", "establishment", "neighborhood",
     "sublocality", "sublocality_level_1", "sublocality_level_2", "locality"}
)
# Nominatim results are precise enough for an H3 cell unless they are a whole administrative area.
NOMINATIM_COARSE = frozenset(
    {"country", "state", "state_district", "region", "province", "county", "district", "municipality", "administrative"}
)


# Google answers these when the key cannot be used (Geocoding API not enabled, no billing, quota gone).
GOOGLE_REFUSED = frozenset({"REQUEST_DENIED", "OVER_DAILY_LIMIT", "OVER_QUERY_LIMIT"})


class GoogleRefused(Exception):
    pass


@dataclass(frozen=True)
class GeocodeHit:
    lat: float
    lon: float
    precise: bool  # locality or finer: good enough for an H3 cell (confidence B)
    label: str


class Geocoder:
    def __init__(self, provider: str = "none", *, google_key: str | None = None, http: httpx.Client | None = None):
        if provider == "auto":
            provider = "google" if google_key else "nominatim"
        if provider == "google" and not google_key:
            log.warning("GEOCODER=google but GOOGLE_MAPS_API_KEY is not set: using Nominatim")
            provider = "nominatim"
        self.name = provider  # google | nominatim | none
        self._key = google_key
        self._http = http or httpx.Client(timeout=8.0, headers={"User-Agent": USER_AGENT})
        self._lock = threading.Lock()
        self._last = 0.0
        self._cache: dict[tuple[str, str, str], GeocodeHit | None] = {}

    @property
    def enabled(self) -> bool:
        return self.name != "none"

    def geocode(self, query: str, country: str, region: str | None = None) -> GeocodeHit | None:
        """`country` is ISO 3166-1 alpha-2; `region` (a state name) narrows the search."""
        query = " ".join(query.split())[:200]
        if not self.enabled or not query:
            return None
        key = (query.casefold(), country, (region or "").casefold())
        if key in self._cache:
            return self._cache[key]
        try:
            try:
                hit = self._google(query, country, region) if self.name == "google" else self._nominatim(query, country, region)
            except GoogleRefused as exc:
                # A refused key would otherwise make every place "not found"; say why once and use OpenStreetMap.
                log.error("Google Geocoding refused the key (%s); using OpenStreetMap Nominatim instead. Enable the "
                          "Geocoding API for this key in Google Cloud and restart to use Google.", exc)
                self.name = "nominatim"
                hit = self._nominatim(query, country, region)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("geocoding failed (%s): %s", self.name, exc)
            return None
        if len(self._cache) > 2000:
            self._cache.clear()
        self._cache[key] = hit
        return hit

    def _google(self, query: str, country: str, region: str | None) -> GeocodeHit | None:
        components = f"country:{country}" + (f"|administrative_area:{region}" if region else "")
        response = self._http.get(GOOGLE_URL, params={"address": query, "components": components, "key": self._key})
        response.raise_for_status()
        data = response.json()
        if data.get("status") in GOOGLE_REFUSED:
            raise GoogleRefused(f"{data.get('status')}: {data.get('error_message', '')[:160]}")
        if data.get("status") != "OK" or not data.get("results"):
            return None
        top = data["results"][0]
        location = top["geometry"]["location"]
        return GeocodeHit(float(location["lat"]), float(location["lng"]), bool(GOOGLE_PRECISE & set(top.get("types", []))),
                          top.get("formatted_address", query))

    def _nominatim(self, query: str, country: str, region: str | None) -> GeocodeHit | None:
        with self._lock:  # one request per second, as the usage policy asks
            wait = 1.0 - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            q = ", ".join(part for part in (query, region) if part)
            response = self._http.get(NOMINATIM_URL, params={
                "q": q, "countrycodes": country.lower(), "format": "jsonv2", "limit": 1, "accept-language": "en",
            })
        response.raise_for_status()
        results = response.json()
        if not results:
            return None
        top = results[0]
        coarse = str(top.get("addresstype", "")) in NOMINATIM_COARSE or top.get("type") == "administrative"
        return GeocodeHit(float(top["lat"]), float(top["lon"]), not coarse, top.get("display_name", query))


def build_geocoder(provider: str, google_key: str | None) -> Geocoder:
    return Geocoder(provider, google_key=google_key)
