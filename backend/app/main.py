"""HTTP API: intake (web, WhatsApp, Telegram), rankings, cluster detail, district views and open-data export.

Run locally from backend/:  uvicorn app.main:app --reload
"""

from __future__ import annotations

import base64
import binascii
import csv
import io
import json
import logging
import threading
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import __version__
from .channels import telegram, whatsapp
from .channels.base import InboundMessage
from .channels.messages import ack_message, welcome_message
from .config import REPO_ROOT, Settings, get_settings
from .container import Container, build_container
from .models import public_view
from .scoring import COMPONENTS, PRESETS, VOLUME_ONLY, Weights
from .taxonomy import SECTOR_DESCRIPTIONS

log = logging.getLogger(__name__)

DASHBOARD = REPO_ROOT / "frontend" / "index.html"
AGGREGATE_FIELDS = ("admin_code", "district", "sector", "h3", "lat", "lon", "n_requests", "n_requesters", "share_urgent", "synthetic_share")


class IngestIn(BaseModel):
    text: str | None = Field(default=None, max_length=4000)
    audio_base64: str | None = Field(default=None, description="Base64 audio (ogg/opus, mp3, wav, webm)")
    audio_mime: str | None = None
    sender_id: str | None = Field(default=None, description="Optional stable ID for the submitter; hashed before storage")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


def resolve_weights(preset: str, overrides: dict[str, float | None]) -> Weights | None:
    """None means the volume-only baseline. Overrides replace individual preset weights; all are renormalised."""
    if preset == VOLUME_ONLY:
        return None
    if preset not in PRESETS:
        raise HTTPException(422, f"unknown preset {preset!r}; use one of {sorted([*PRESETS, VOLUME_ONLY])}")
    values = PRESETS[preset].as_dict()
    values.update({k: v for k, v in overrides.items() if v is not None})
    try:
        return Weights(**values).normalised()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Civic Demand API",
        version=__version__,
        description="Multilingual citizen demand → district fusion → transparent, equity-weighted priorities.",
    )
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"])

    holder: dict[str, Container | None] = {"c": container}
    build_lock = threading.Lock()

    def c() -> Container:
        if holder["c"] is None:
            with build_lock:
                if holder["c"] is None:
                    holder["c"] = build_container(settings)
        return holder["c"]  # type: ignore[return-value]

    app.state.container = c

    # --- dashboard -------------------------------------------------------------------------------

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        """The single-page dashboard; it calls this API from the same origin."""
        if not DASHBOARD.is_file():
            raise HTTPException(404, "dashboard not bundled; see /docs for the API")
        return FileResponse(DASHBOARD, media_type="text/html")

    # --- meta ------------------------------------------------------------------------------------

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/meta")
    def meta() -> dict[str, Any]:
        ctx = c().ctx
        return {
            "pack_id": ctx.pack_id,
            "region": ctx.region_name,
            "languages": ctx.languages,
            "sectors": SECTOR_DESCRIPTIONS,
            "presets": {name: w.as_dict() for name, w in PRESETS.items()} | {VOLUME_ONLY: None},
            "components": COMPONENTS,
            "language_provider": c().provider.name,
            "repository": settings.repository,
            "synthetic_indicators": ctx.synthetic_indicators,
            "placeholder_metrics": sorted({m for ms in ctx.placeholder_metrics.values() for m in ms}),
            "synthetic_planned_projects": ctx.synthetic_planned,
            "summary": c().demand.summary(),
        }

    # --- intake ----------------------------------------------------------------------------------

    @app.post("/ingest", status_code=201)
    def ingest(body: IngestIn) -> dict[str, Any]:
        if not (body.text and body.text.strip()) and not body.audio_base64:
            raise HTTPException(422, "text or audio_base64 is required")
        audio = None
        if body.audio_base64:
            try:
                audio = base64.b64decode(body.audio_base64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise HTTPException(422, "audio_base64 is not valid base64") from exc
        request = c().ingest.ingest(
            channel="web",
            sender_id=body.sender_id,
            text=body.text,
            audio=audio,
            audio_mime=body.audio_mime,
            lat=body.lat,
            lon=body.lon,
        )
        c().demand.invalidate()
        return public_view(request) | {"ack": ack_message(request)}

    @app.get("/requests")
    def list_requests(status: str | None = None, limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
        requests = [r for r in c().repo.all() if status is None or r.status == status]
        requests.sort(key=lambda r: r.created_at, reverse=True)
        return [public_view(r) for r in requests[:limit]]

    @app.get("/requests/{request_id}")
    def get_request(request_id: str) -> dict[str, Any]:
        request = c().repo.get(request_id)
        if request is None:
            raise HTTPException(404, "request not found")
        return public_view(request)

    # --- rankings --------------------------------------------------------------------------------

    @app.get("/rankings")
    def rankings(
        preset: str = "balanced",
        demand: float | None = Query(None, ge=0),
        need: float | None = Query(None, ge=0),
        equity: float | None = Query(None, ge=0),
        alignment: float | None = Query(None, ge=0),
        urgency: float | None = Query(None, ge=0),
        sector: str | None = None,
        admin_code: str | None = None,
        limit: int = Query(20, ge=1, le=500),
        sensitivity: bool = True,
    ) -> dict[str, Any]:
        overrides = {"demand": demand, "need": need, "equity": equity, "alignment": alignment, "urgency": urgency}
        weights = resolve_weights(preset, overrides)
        items = c().demand.rankings(weights, sector=sector, admin_code=admin_code, limit=limit, sensitivity=sensitivity)
        return {"preset": preset, "weights": weights.as_dict() if weights else None, "items": items}

    @app.get("/rankings/compare")
    def compare(a: str = VOLUME_ONLY, b: str = "equity_first", k: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
        for preset in (a, b):
            if preset != VOLUME_ONLY and preset not in PRESETS:
                raise HTTPException(422, f"unknown preset {preset!r}")
        return c().demand.compare(a, b, k)

    @app.get("/clusters/{cluster_id}")
    def cluster(cluster_id: str, preset: str = "balanced") -> dict[str, Any]:
        weights = resolve_weights(preset, {}) or PRESETS["balanced"]
        view = c().demand.cluster(cluster_id, weights)
        if view is None:
            raise HTTPException(404, "cluster not found")
        return view

    @app.get("/districts")
    def districts() -> list[dict[str, Any]]:
        return c().demand.districts()

    @app.get("/districts/silent")
    def silent_districts(k: int = Query(5, ge=1, le=50)) -> list[dict[str, Any]]:
        return c().demand.silent_districts(k)

    # --- open data export (DPG indicator 6) ------------------------------------------------------

    @app.get("/export/aggregates.csv")
    def export_csv(level: str = Query("district", pattern="^(district|h3)$")) -> Response:
        rows, suppressed = c().demand.aggregates(level, settings.export_min_requesters)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=AGGREGATE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            buffer.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="aggregates_{level}.csv"',
                "X-Suppressed-Groups": str(suppressed),
            },
        )

    @app.get("/export/aggregates.geojson")
    def export_geojson(level: str = Query("district", pattern="^(district|h3)$")) -> dict[str, Any]:
        import h3

        rows, suppressed = c().demand.aggregates(level, settings.export_min_requesters)
        features = []
        for row in rows:
            if row["h3"]:
                ring = [[lon, lat] for lat, lon in h3.cell_to_boundary(row["h3"])]
                geometry = {"type": "Polygon", "coordinates": [ring + ring[:1]]}
            else:
                geometry = {"type": "Point", "coordinates": [row["lon"], row["lat"]]}
            features.append({"type": "Feature", "geometry": geometry, "properties": row})
        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {"level": level, "min_requesters": settings.export_min_requesters, "suppressed_groups": suppressed},
        }

    # --- WhatsApp --------------------------------------------------------------------------------

    def handle_whatsapp(message: InboundMessage) -> None:
        try:
            container_ = c()
            audio = mime = None
            if message.media_id:
                if container_.whatsapp is None:
                    log.warning("voice note received but WhatsApp credentials are not configured")
                    return
                audio, mime = container_.whatsapp.download_media(message.media_id)
            if not message.text and audio is None:
                return
            request = container_.ingest.ingest(
                channel="whatsapp", sender_id=message.sender_id, text=message.text,
                audio=audio, audio_mime=mime, lat=message.lat, lon=message.lon,
            )
            container_.demand.invalidate()
            if container_.whatsapp:
                container_.whatsapp.send_text(message.reply_to, ack_message(request))
        except Exception:
            log.exception("failed to process WhatsApp message %s", message.message_id)

    @app.get("/webhooks/whatsapp", response_class=PlainTextResponse)
    def whatsapp_verify(
        mode: str = Query("", alias="hub.mode"),
        token: str = Query("", alias="hub.verify_token"),
        challenge: str = Query("", alias="hub.challenge"),
    ) -> str:
        if mode == "subscribe" and settings.whatsapp_verify_token and token == settings.whatsapp_verify_token:
            return challenge
        raise HTTPException(403, "verification failed")

    @app.post("/webhooks/whatsapp")
    async def whatsapp_inbound(request: Request, background: BackgroundTasks) -> dict[str, str]:
        body = await request.body()
        if settings.whatsapp_app_secret and not whatsapp.verify_signature(
            settings.whatsapp_app_secret, body, request.headers.get("X-Hub-Signature-256")
        ):
            raise HTTPException(403, "invalid signature")
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "invalid JSON") from exc
        for message in whatsapp.parse_webhook(payload):
            if message.has_content:
                background.add_task(handle_whatsapp, message)
        return {"status": "ok"}  # always 200 quickly, or Meta retries

    # --- Telegram --------------------------------------------------------------------------------

    def handle_telegram(message: InboundMessage) -> None:
        try:
            container_ = c()
            bot = container_.telegram
            if message.text and message.text.strip().startswith("/"):
                if bot:
                    bot.send_text(message.reply_to, welcome_message())
                return
            audio = None
            if message.media_id:
                if bot is None:
                    log.warning("voice note received but TELEGRAM_BOT_TOKEN is not set")
                    return
                audio = bot.download_file(message.media_id)
            request = container_.ingest.ingest(
                channel="telegram", sender_id=message.sender_id, text=message.text,
                audio=audio, audio_mime=message.media_mime, lat=message.lat, lon=message.lon,
            )
            container_.demand.invalidate()
            if bot:
                bot.send_text(message.reply_to, ack_message(request))
        except Exception:
            log.exception("failed to process Telegram message %s", message.message_id)

    @app.post("/webhooks/telegram")
    async def telegram_inbound(request: Request, background: BackgroundTasks) -> dict[str, str]:
        if settings.telegram_webhook_secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != settings.telegram_webhook_secret:
            raise HTTPException(403, "invalid secret token")
        message = telegram.parse_update(await request.json())
        if message and message.has_content:
            background.add_task(handle_telegram, message)
        return {"status": "ok"}

    return app


app = create_app()
