"""WhatsApp Cloud API: webhook parsing, signature check, media download and text replies.

Note: Meta prices service messages per delivered message in India from 1 Oct 2026; budget for it at scale.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from .base import InboundMessage


def parse_webhook(payload: dict[str, Any]) -> list[InboundMessage]:
    messages = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            for m in (change.get("value") or {}).get("messages", []) or []:
                sender = str(m.get("from", ""))
                base = {"sender_id": sender, "reply_to": sender, "message_id": str(m.get("id", ""))}
                kind = m.get("type")
                if kind == "text":
                    messages.append(InboundMessage(**base, text=(m.get("text") or {}).get("body")))
                elif kind in ("audio", "voice"):
                    media = m.get(kind) or {}
                    messages.append(InboundMessage(**base, media_id=media.get("id"), media_mime=media.get("mime_type")))
                elif kind == "location":
                    loc = m.get("location") or {}
                    text = " ".join(p for p in (loc.get("name"), loc.get("address")) if p) or None
                    messages.append(InboundMessage(**base, text=text, lat=loc.get("latitude"), lon=loc.get("longitude")))
    return messages


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str, graph_version: str = "v21.0", timeout: float = 20.0):
        self._phone_number_id = phone_number_id
        self._http = httpx.Client(
            base_url=f"https://graph.facebook.com/{graph_version}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
        )

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        meta = self._http.get(f"/{media_id}")
        meta.raise_for_status()
        info = meta.json()
        blob = self._http.get(info["url"])  # short-lived URL; needs the same bearer token
        blob.raise_for_status()
        return blob.content, info.get("mime_type", "audio/ogg")

    def send_text(self, to: str, body: str) -> None:
        response = self._http.post(
            f"/{self._phone_number_id}/messages",
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}},
        )
        response.raise_for_status()
