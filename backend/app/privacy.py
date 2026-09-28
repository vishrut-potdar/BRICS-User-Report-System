"""PII minimisation: requester hashing and regex redaction (a backstop to Gemini's redacted summary)."""

from __future__ import annotations

import hashlib
import hmac
import re

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)"), "[id-number]"),  # Aadhaar-shaped
    (re.compile(r"(?<![\w+])\+?\d[\d\s-]{8,}\d(?!\w)"), "[phone]"),
)


def hash_requester(channel: str, sender_id: str, salt: str) -> str:
    """Stable pseudonymous requester ID. Rotating the salt unlinks every past hash."""
    message = f"{channel}:{sender_id.strip()}".encode()
    return hmac.new(salt.encode(), message, hashlib.sha256).hexdigest()[:24]


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text
