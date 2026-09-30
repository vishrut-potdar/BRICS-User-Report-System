"""Normalises any inbound message (web portal, WhatsApp, Telegram) into stored CivicRequests.

One message is read by the language provider once, then filed into every pack of its country that it falls in:
always the country pack (state level), and a pilot pack (district level) when it is inside that pilot region.
Each copy has the same tracking ID. Raw audio is never stored: it is passed to the provider and dropped.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from .language import ExtractionError
from .language.base import Extraction
from .models import CivicRequest, Geo
from .privacy import hash_requester, redact

if TYPE_CHECKING:
    from .container import Container, Region

log = logging.getLogger(__name__)

# WhatsApp sender IDs are international numbers without "+": route them to a country by calling code.
CALLING_CODES = {"55": "BR", "7": "RU", "91": "IN", "86": "CN", "27": "ZA"}


def country_for_number(number: str | None) -> str | None:
    digits = "".join(c for c in number or "" if c.isdigit())
    for prefix in sorted(CALLING_CODES, key=len, reverse=True):
        if digits.startswith(prefix):
            return CALLING_CODES[prefix]
    return None


def _selected_code(region: Region, admin_code: str | None) -> str | None:
    """Map a unit the citizen picked (at any level) onto this pack's units.

    A pilot district (BR-AL-MACEIO) rolls up to its state (BR-AL) in the country pack. A state picked in the
    country pack says nothing about which district inside a pilot, so the pilot resolves that itself."""
    if not admin_code:
        return None
    if admin_code in region.ctx.info:
        return admin_code
    for code in region.ctx.info:
        if admin_code.startswith(code + "-"):
            return code
    return None


class IngestService:
    def __init__(self, container: Container, salt: str):
        self._c = container
        self._salt = salt

    def ingest(self, **kwargs) -> CivicRequest:
        """The most specific stored copy (pilot if the message fell inside one, else country)."""
        return self.ingest_all(**kwargs)[0]

    def ingest_all(
        self,
        *,
        channel: str,
        sender_id: str | None,
        text: str | None = None,
        audio: bytes | None = None,
        audio_mime: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        pack: str | None = None,
        country: str | None = None,
        admin_code: str | None = None,
        category: str | None = None,
        location_text: str | None = None,
        location_confidence: str = "A",
    ) -> tuple[CivicRequest, dict[str, CivicRequest]]:
        """`location_text` is a place the citizen typed; `location_confidence` is A for device GPS and B for a pin
        they placed on the map or a searched place."""
        c = self._c
        country = country or c.country_of(pack or c.settings.pack_id)
        pack_ids = c.packs_for_country(country) or [c.settings.pack_id]
        provider = c.provider_for(c.country_of(pack_ids[0]))
        requester_hash = hash_requester(channel, sender_id or f"anonymous-{uuid4().hex}", self._salt)
        request_id = uuid4().hex[:12]

        try:
            extraction: Extraction | None = provider.extract(text=text, audio=audio, audio_mime=audio_mime)
        except ExtractionError as exc:
            log.warning("extraction failed, sending to review: %s", exc)
            extraction = None
        if extraction is not None and category:
            extraction = extraction.model_copy(update={"category": category})  # the citizen's own choice wins

        stored: dict[str, CivicRequest] = {}
        for pack_id in pack_ids:
            region = c.region(pack_id)
            geo = self._geo(region, extraction, text, lat, lon, admin_code, location_text, location_confidence)
            is_country = region.ctx.level == "country" or len(pack_ids) == 1
            if not geo.admin_code and not is_country:
                continue  # outside this pilot region
            if extraction is None:
                request = CivicRequest(
                    id=request_id, channel=channel, lang="und", text_original=redact(text or "[audio]"), text_en="",
                    category=category or "other", geo=geo, requester_hash=requester_hash, status="needs_review",
                    provider=provider.name,
                )
            else:
                request = CivicRequest(
                    id=request_id,
                    channel=channel,
                    lang=extraction.lang,
                    code_mixed=extraction.code_mixed,
                    text_original=redact(extraction.transcript or text or ""),
                    text_en=redact(extraction.text_en),
                    category=extraction.category,
                    sub_type=extraction.sub_type,
                    urgency=extraction.urgency,
                    summary_redacted=redact(extraction.summary_redacted),
                    geo=geo,
                    requester_hash=requester_hash,
                    status="received" if geo.admin_code else "needs_review",
                    provider=provider.name,
                )
            region.repo.add(request)
            region.demand.invalidate()
            stored[pack_id] = request

        primary = next((stored[p] for p in reversed(pack_ids) if p in stored and stored[p].geo.admin_code), None)
        return primary or next(iter(stored.values())), stored

    @staticmethod
    def _geo(region: Region, extraction: Extraction | None, text: str | None, lat: float | None, lon: float | None,
             admin_code: str | None, location_text: str | None = None, location_confidence: str = "A") -> Geo:
        selected = _selected_code(region, admin_code)
        common = {"lat": lat, "lon": lon, "typed_location": location_text, "point_confidence": location_confidence,
                  "hint": [region.ctx.info[selected].name] if selected else []}
        if extraction is None:
            geo = region.resolver.resolve(transcript=text or "", **common)
        else:
            geo = region.resolver.resolve(
                mentions=extraction.location_mentions, district_guess=extraction.district_guess,
                transcript=extraction.transcript or text or "", **common,
            )
        if selected and geo.admin_code != selected:
            # The citizen's own choice beats text matching; a GPS pin elsewhere keeps its cell but not its district.
            geo = geo.model_copy(update={
                "admin_code": selected, "district": region.ctx.info[selected].name,
                "method": geo.method if geo.lat is not None else "selected",
            })
        return geo
