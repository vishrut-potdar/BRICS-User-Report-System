"""Telegram Bot API: the no-approval fallback channel for the live demo."""

from __future__ import annotations

from typing import Any

import httpx

from .base import InboundMessage


def parse_update(update: dict[str, Any]) -> InboundMessage | None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return None
    sender = str((message.get("from") or {}).get("id", ""))
    chat = str((message.get("chat") or {}).get("id", sender))
    voice = message.get("voice") or message.get("audio") or {}
    location = message.get("location") or {}
    return InboundMessage(
        sender_id=sender,
        reply_to=chat,
        message_id=str(message.get("message_id", "")),
        text=message.get("text") or message.get("caption"),
        media_id=voice.get("file_id"),
        media_mime=voice.get("mime_type", "audio/ogg") if voice else None,
        lat=location.get("latitude"),
        lon=location.get("longitude"),
    )


class TelegramClient:
    def __init__(self, token: str, timeout: float = 20.0):
        self._token = token
        self._http = httpx.Client(timeout=timeout)

    def _api(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    def download_file(self, file_id: str) -> bytes:
        response = self._http.get(self._api("getFile"), params={"file_id": file_id})
        response.raise_for_status()
        path = response.json()["result"]["file_path"]
        blob = self._http.get(f"https://api.telegram.org/file/bot{self._token}/{path}")
        blob.raise_for_status()
        return blob.content

    def send_text(self, chat_id: str, text: str) -> None:
        self._http.post(self._api("sendMessage"), json={"chat_id": chat_id, "text": text}).raise_for_status()
