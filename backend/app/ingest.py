"""Normalises any inbound message (web, WhatsApp, Telegram) into one stored CivicRequest.

Raw audio is never stored: it is passed to the language provider and dropped.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from .geo import GeoResolver
from .language import ExtractionError, LanguageProvider
from .models import CivicRequest, Geo
from .privacy import hash_requester, redact
from .repository import RequestRepository

log = logging.getLogger(__name__)


class IngestService:
    def __init__(self, provider: LanguageProvider, resolver: GeoResolver, repo: RequestRepository, salt: str):
        self._provider = provider
        self._resolver = resolver
        self._repo = repo
        self._salt = salt

    def ingest(
        self,
        *,
        channel: str,
        sender_id: str | None,
        text: str | None = None,
        audio: bytes | None = None,
        audio_mime: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> CivicRequest:
        requester_hash = hash_requester(channel, sender_id or f"anonymous-{uuid4().hex}", self._salt)
        try:
            extraction = self._provider.extract(text=text, audio=audio, audio_mime=audio_mime)
        except ExtractionError as exc:
            log.warning("extraction failed, sending to review: %s", exc)
            geo = self._resolver.resolve(lat=lat, lon=lon, transcript=text or "")
            request = CivicRequest(
                channel=channel,
                lang="und",
                text_original=redact(text or "[audio]"),
                text_en="",
                category="other",
                geo=geo,
                requester_hash=requester_hash,
                status="needs_review",
                provider=self._provider.name,
            )
            self._repo.add(request)
            return request

        geo: Geo = self._resolver.resolve(
            lat=lat,
            lon=lon,
            mentions=extraction.location_mentions,
            district_guess=extraction.district_guess,
            transcript=extraction.transcript,
        )
        request = CivicRequest(
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
            provider=self._provider.name,
        )
        self._repo.add(request)
        return request
