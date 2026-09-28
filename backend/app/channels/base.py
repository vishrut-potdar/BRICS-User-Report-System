from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InboundMessage:
    sender_id: str  # hashed before storage; never persisted raw
    reply_to: str  # WhatsApp wa_id or Telegram chat id
    message_id: str = ""
    text: str | None = None
    media_id: str | None = None
    media_mime: str | None = None
    lat: float | None = None
    lon: float | None = None

    @property
    def has_content(self) -> bool:
        return bool((self.text and self.text.strip()) or self.media_id)
