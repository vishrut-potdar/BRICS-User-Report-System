"""The open core schema. See docs/schema.md for field semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .taxonomy import Sector

Channel = Literal["whatsapp", "telegram", "web", "ivr", "sms"]
Urgency = Literal["low", "medium", "high"]
GeoConfidence = Literal["A", "B", "C"]  # A = device GPS, B = geocoded landmark, C = district-level only
Status = Literal["received", "needs_review", "forwarded", "in_progress", "resolved", "rejected"]


class Geo(BaseModel):
    lat: float | None = None
    lon: float | None = None
    h3: str | None = None
    admin_code: str | None = None  # ISO 3166-2 region + district slug, e.g. IN-MH-PUNE
    district: str | None = None
    location_text: str | None = None
    confidence: GeoConfidence = "C"
    method: str = "none"  # gps | geocode | gazetteer | none


class CivicRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    channel: Channel
    lang: str  # BCP-47: mr, hi, en, hi-Latn (Hindi in Roman script), und
    code_mixed: bool = False
    text_original: str  # transcript or text, with phone numbers / IDs / emails redacted
    text_en: str
    category: Sector
    sub_type: str = ""
    urgency: Urgency = "low"
    summary_redacted: str = ""
    geo: Geo = Field(default_factory=Geo)
    requester_hash: str  # HMAC of channel + sender id; the raw number is never stored
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Status = "received"
    provider: str = ""  # which language provider structured it: gemini | offline | synthetic
    synthetic: bool = False


def public_view(request: CivicRequest) -> dict[str, Any]:
    """What the API exposes about a single request: no requester hash, no original text."""
    return {
        "id": request.id,
        "channel": request.channel,
        "lang": request.lang,
        "category": request.category,
        "sub_type": request.sub_type,
        "urgency": request.urgency,
        "summary": request.summary_redacted,
        "district": request.geo.district,
        "admin_code": request.geo.admin_code,
        "h3": request.geo.h3,
        "location_confidence": request.geo.confidence,
        "created_at": request.created_at.isoformat(),
        "status": request.status,
        "synthetic": request.synthetic,
    }
