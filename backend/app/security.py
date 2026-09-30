"""HTTP hardening: security headers, per-client rate limits and the optional admin token.

- Headers: no MIME sniffing, no framing, a strict referrer policy, geolocation and microphone only for this site,
  and a Content-Security-Policy on the HTML pages that allows exactly the third parties they use (Google Fonts,
  Leaflet on unpkg, OpenStreetMap tiles, Google Maps).
- Rate limits: a sliding one-minute window per client for the endpoints that cost money or hit third parties
  (Gemini, the geocoder) or write data. In-memory, so per instance; put Cloud Armor or an API gateway in front for
  a real deployment.
- Admin token: when ADMIN_TOKEN is set, officials' actions (status changes, AI briefings) need the header
  X-Admin-Token. Without it they are open, which is fine for a local demo and logged as a warning.
"""

from __future__ import annotations

import hmac
import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

log = logging.getLogger(__name__)

GOOGLE = "https://*.googleapis.com https://*.gstatic.com https://*.google.com https://*.ggpht.com"
CSP = "; ".join([
    "default-src 'self'",
    f"script-src 'self' 'unsafe-inline' https://unpkg.com {GOOGLE}",
    f"style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com {GOOGLE}",
    "font-src 'self' https://fonts.gstatic.com data:",
    f"img-src 'self' data: blob: https://tile.openstreetmap.org https://unpkg.com {GOOGLE}",
    f"connect-src 'self' {GOOGLE}",
    "worker-src blob:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(self), microphone=(self), camera=()",
}
# path prefix -> requests per minute per client
LIMITS = {"/ingest": 20, "/assist/": 20, "/geocode": 30, "/clusters/": 60}


def client_id(request: Request) -> str:
    """The caller's address. Behind a proxy (Cloud Run), the first X-Forwarded-For hop is the client."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for key, value in HEADERS.items():
            response.headers.setdefault(key, value)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers.setdefault("Content-Security-Policy", CSP)
        return response


class RateLimit(BaseHTTPMiddleware):
    def __init__(self, app, per_minute_scale: float = 1.0):
        super().__init__(app)
        self._scale = per_minute_scale
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(self, request, call_next):
        if request.method == "POST" or request.url.path.startswith("/geocode"):
            rule = next((p for p in LIMITS if request.url.path.startswith(p)), None)
            if rule and self._scale > 0:
                limit = max(1, int(LIMITS[rule] * self._scale))
                key, now = (client_id(request), rule), time.monotonic()
                with self._lock:
                    hits = self._hits[key]
                    while hits and now - hits[0] > 60:
                        hits.popleft()
                    if len(hits) >= limit:
                        retry = int(60 - (now - hits[0])) + 1
                        return JSONResponse({"detail": "too many requests, please wait a moment"}, status_code=429,
                                            headers={"Retry-After": str(retry)})
                    hits.append(now)
                    if len(self._hits) > 50_000:  # forget idle clients
                        for stale in [k for k, v in self._hits.items() if not v or now - v[-1] > 60]:
                            del self._hits[stale]
        return await call_next(request)


def admin_guard(token: str | None):
    """FastAPI dependency: require X-Admin-Token when ADMIN_TOKEN is configured."""
    if not token:
        log.warning("ADMIN_TOKEN is not set: officials' actions (status changes, AI briefings) are open to anyone")

    def check(x_admin_token: str | None = Header(default=None)) -> None:
        if token and not (x_admin_token and hmac.compare_digest(x_admin_token, token)):
            raise HTTPException(401, "admin token required", headers={"WWW-Authenticate": "X-Admin-Token"})
    return check
