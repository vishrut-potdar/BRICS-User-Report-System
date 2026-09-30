"""HTTP API: intake (web portal, WhatsApp, Telegram), rankings, cluster detail, district views and open-data export.

Every read endpoint takes ?pack=<PACK_ID> (default: PACK_ID). A pack is a country (units = states/provinces) or a
pilot region (units = districts). GET /packs lists them.

Pages: / is the citizen complaint portal, /admin the government dashboard.

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
from typing import Any, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, assist
from .channels import telegram, whatsapp
from .channels.base import InboundMessage
from .channels.messages import ack_message, welcome_message
from .config import REPO_ROOT, Settings, get_settings
from .container import Container, Region, UnknownPack, build_container
from .ingest import country_for_number
from .models import public_view
from .taxonomy import Sector
from .scoring import COMPONENTS, PRESETS, VOLUME_ONLY, Weights
from .security import RateLimit, SecurityHeaders, admin_guard
from .taxonomy import SECTOR_DESCRIPTIONS

log = logging.getLogger(__name__)

FRONTEND = REPO_ROOT / "frontend"
# Pages link to each other and to app.css relatively, so they also work when opened from disk.
PAGES = {"/": "index.html", "/index.html": "index.html", "/admin": "admin.html", "/admin.html": "admin.html"}
AGGREGATE_FIELDS = ("admin_code", "district", "sector", "h3", "lat", "lon", "n_requests", "n_requesters", "share_urgent", "synthetic_share")


class IngestIn(BaseModel):
    text: str | None = Field(default=None, max_length=4000)
    audio_base64: str | None = Field(default=None, max_length=14_000_000, description="Base64 audio (ogg/opus, mp3, wav, webm), up to about 10 MB")
    audio_mime: str | None = None
    sender_id: str | None = Field(default=None, description="Optional stable ID for the submitter; hashed before storage")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    pack: str | None = Field(default=None, description="Pack the citizen is filing in; its country decides routing")
    admin_code: str | None = Field(default=None, description="State or district the citizen picked, e.g. BR-AL or BR-AL-MACEIO")
    category: Sector | None = Field(default=None, description="Sector the citizen picked; overrides automatic classification")
    location_text: str | None = Field(default=None, max_length=200, description="Place the citizen typed: village, ward, landmark")
    location_confidence: Literal["A", "B"] = Field(default="A", description="A = device GPS; B = a pin they placed or a searched place")


class UnderstandIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    pack: str | None = None


class BriefIn(BaseModel):
    pack: str | None = None
    cluster_id: str | None = Field(default=None, description="Brief one cluster; omit for the whole area")
    admin_code: str | None = Field(default=None, description="Area to brief on (a unit of the pack); omit for the whole pack")
    lang: str = Field(default="en", max_length=12)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(received|forwarded|in_progress|resolved)$")


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


def pack_summary(container: Container, pack_id: str) -> dict[str, Any]:
    config = container.config(pack_id)
    return {
        "pack_id": pack_id,
        "country": config["country"],
        "country_name": config.get("country_name", config["country"]),
        "level": config.get("level", "region"),
        "parent": config.get("parent"),
        "region_name": config["region_name"],
        "unit_label": config.get("unit_label", "district"),
        "unit_label_plural": config.get("unit_label_plural", "districts"),
        "priority_label": config.get("priority_label"),
        "languages": config.get("languages", []),
    }


def local_language(container: Container, country: str | None = None) -> str | None:
    """The main language of a country: the first one its country pack lists (Hindi for India)."""
    country = country or container.country_of(container.settings.pack_id)
    packs = container.packs_for_country(country)
    languages = container.config(packs[0]).get("languages", []) if packs else []
    return languages[0] if languages else None


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Civic Demand API",
        version=__version__,
        description="Multilingual citizen demand → district fusion → transparent, equity-weighted priorities, for BRICS countries.",
    )
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(GZipMiddleware, minimum_size=1024)  # boundaries and rankings shrink about 5x
    app.add_middleware(RateLimit, per_minute_scale=settings.rate_limit_scale)
    app.add_middleware(SecurityHeaders)
    require_admin = Depends(admin_guard(settings.admin_token))

    holder: dict[str, Container | None] = {"c": container}
    build_lock = threading.Lock()

    def c() -> Container:
        if holder["c"] is None:
            with build_lock:
                if holder["c"] is None:
                    holder["c"] = build_container(settings)
        return holder["c"]  # type: ignore[return-value]

    def reg(pack: str | None) -> Region:
        try:
            return c().region(pack)
        except UnknownPack as exc:
            raise HTTPException(404, f"unknown pack {pack!r}; see /packs") from exc

    app.state.container = c

    # --- pages -------------------------------------------------------------------------------------

    def page(name: str, media_type: str = "text/html"):
        def serve() -> FileResponse:
            path = FRONTEND / name
            if not path.is_file():
                raise HTTPException(404, "page not bundled; see /docs for the API")
            # Revalidate every time so browsers never run an old copy of the page or its scripts after an update.
            return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-cache"})
        return serve

    app.add_api_route("/app.css", page("app.css", "text/css"), methods=["GET"], include_in_schema=False)
    app.add_api_route("/map.js", page("map.js", "text/javascript"), methods=["GET"], include_in_schema=False)

    for route, name in PAGES.items():
        app.add_api_route(route, page(name), methods=["GET"], include_in_schema=False)
    if FRONTEND.is_dir():
        app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    # --- meta ------------------------------------------------------------------------------------

    @app.get("/health")
    def health() -> dict[str, Any]:
        """Liveness plus a deployment check: are the pages and the region data present on this server?"""
        return {
            "status": "ok",
            "version": __version__,
            "pages": all((FRONTEND / name).is_file() for name in ("index.html", "admin.html", "app.css", "map.js")),
            "data": (settings.data_dir / "packs").is_dir() and any((settings.data_dir / "packs").glob("*.json")),
        }

    @app.get("/packs")
    def packs() -> list[dict[str, Any]]:
        """Every pack served: countries (level=country) and their pilot regions (parent = country pack)."""
        return [pack_summary(c(), p) for p in c().pack_ids]

    @app.get("/meta")
    def meta(pack: str | None = None) -> dict[str, Any]:
        region = reg(pack)
        ctx = region.ctx
        return pack_summary(c(), ctx.pack_id) | {
            "default_pack": settings.pack_id,
            "sectors": SECTOR_DESCRIPTIONS,
            "presets": {name: w.as_dict() for name, w in PRESETS.items()} | {VOLUME_ONLY: None},
            "components": COMPONENTS,
            "language_provider": c().provider_for(ctx.country).name,
            "repository": settings.repository,
            "synthetic_indicators": ctx.synthetic_indicators,
            "placeholder_metrics": sorted({m for ms in ctx.placeholder_metrics.values() for m in ms}),
            "synthetic_planned_projects": ctx.synthetic_planned,
            "units": [
                {"admin_code": code, "name": info.name, "name_local": info.name_local, "centroid": {"lat": info.lat, "lon": info.lon}}
                for code, info in sorted(ctx.info.items(), key=lambda kv: kv[1].name)
            ],
            "summary": region.demand.summary(),
        }

    @app.get("/config")
    def client_config() -> dict[str, Any]:
        """What the pages need to pick a map and label AI features. The browser key is meant to be public
        (restrict it by HTTP referrer in Google Cloud); the server geocoding key is never returned."""
        key = settings.google_maps_browser_key
        provider = c().provider_for(c().country_of(settings.pack_id)).name
        return {
            "maps": {"provider": "google" if key else "osm", "browser_key": key},
            "geocoder": c().geocoder.name,
            "ai": {"provider": provider, "enabled": provider == "gemini"},
            "admin_token_required": bool(settings.admin_token),
        }

    def region_for(country_pack: str | None, admin_code: str | None) -> Region:
        """The most detailed pack for a picked unit: the pilot if the unit is (inside) a pilot region."""
        region = reg(country_pack)
        if admin_code:
            for pack_id in c().packs_for_country(region.ctx.country):
                if admin_code == pack_id or admin_code.startswith(pack_id + "-"):
                    if c().config(pack_id).get("level") == "region":
                        return c().region(pack_id)
        return region

    @app.get("/geocode")
    def geocode(q: str = Query(min_length=2, max_length=200), pack: str | None = None, admin_code: str | None = None) -> dict[str, Any]:
        """Find a typed place near the unit the citizen picked, for the portal's map preview."""
        region = region_for(pack, admin_code)
        hint = [region.ctx.info[admin_code].name] if admin_code in region.ctx.info else []
        hit = region.resolver.geocode(q, hint)
        if hit is None:
            raise HTTPException(404, "place not found")
        code = region.resolver.district_for_point(hit.lat, hit.lon)
        return {"lat": round(hit.lat, 6), "lon": round(hit.lon, 6), "label": hit.label, "precise": hit.precise,
                "admin_code": code, "district": region.ctx.info[code].name if code else None,
                "geocoder": c().geocoder.name}

    @app.get("/points")
    def points(pack: str | None = None, admin_code: str | None = None, limit: int = Query(5000, ge=1, le=20000)) -> dict[str, Any]:
        """Where complaints were made: active requests with a GPS pin or a found place, rounded to about 100 m so
        no home can be singled out. Fields: lat, lon, sector, urgency, status, admin_code."""
        from .clustering import is_active

        rows = []
        for r in reg(pack).repo.all():
            if r.geo.lat is None or not is_active(r) or (admin_code and r.geo.admin_code != admin_code):
                continue
            rows.append([round(r.geo.lat, 3), round(r.geo.lon, 3), r.category, r.urgency, r.status, r.geo.admin_code])
            if len(rows) >= limit:
                break
        return {"fields": ["lat", "lon", "sector", "urgency", "status", "admin_code"], "points": rows}

    # --- generative AI assist (Gemini when configured, templates otherwise) --------------------

    @app.post("/assist/understand")
    def assist_understand(body: UnderstandIn) -> dict[str, Any]:
        """Read a draft complaint before it is filed: language, sector, urgency, English translation, places."""
        region = reg(body.pack)
        try:
            return assist.understand(c().provider_for(region.ctx.country), body.text)
        except Exception as exc:  # the provider could not read it; the citizen can still file
            raise HTTPException(422, f"could not read the text: {exc}") from exc

    @app.post("/assist/brief", dependencies=[require_admin])
    def assist_brief(body: BriefIn) -> dict[str, Any]:
        """A short briefing for officials, on one cluster or on a whole area. It never changes the ranking."""
        region = reg(body.pack)
        provider = c().provider_for(region.ctx.country)
        if body.admin_code and body.admin_code not in region.ctx.info:
            raise HTTPException(404, "unknown area for this pack")
        area = region.ctx.info[body.admin_code].name if body.admin_code else region.ctx.region_name
        if body.cluster_id:
            view = region.demand.cluster(body.cluster_id, PRESETS["balanced"])
            if view is None:
                raise HTTPException(404, "cluster not found")
            return assist.cluster_brief(provider, view, area, body.lang) | {"scope": "cluster"}
        items = region.demand.rankings(PRESETS["balanced"], admin_code=body.admin_code, limit=40, sensitivity=False)
        rows = [d for d in region.demand.districts() if not body.admin_code or d["admin_code"] == body.admin_code]
        silent = [] if body.admin_code else region.demand.silent_districts(4)
        return assist.area_brief(provider, area, items, rows, silent, body.lang) | {"scope": "area"}

    @app.get("/boundaries")
    def boundaries(pack: str | None = None) -> FileResponse:
        """GeoJSON polygons of the pack's units (properties: admin_code, name, name_local)."""
        path = reg(pack).ctx.boundaries_path
        if path is None:
            raise HTTPException(404, "no boundaries file for this pack")
        return FileResponse(path, media_type="application/geo+json")

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
        if body.pack:
            reg(body.pack)  # 404 on an unknown pack
        request, stored = c().ingest.ingest_all(
            channel="web",
            sender_id=body.sender_id,
            text=body.text,
            audio=audio,
            audio_mime=body.audio_mime,
            lat=body.lat,
            lon=body.lon,
            pack=body.pack,
            admin_code=body.admin_code,
            category=body.category,
            location_text=body.location_text,
            location_confidence=body.location_confidence,
        )
        ack = ack_message(request, local_language(c(), c().country_of(next(iter(stored)))))
        return public_view(request) | {"ack": ack, "packs": {p: r.geo.admin_code for p, r in stored.items()}}

    @app.get("/requests")
    def list_requests(pack: str | None = None, status: str | None = None, limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
        requests = [r for r in reg(pack).repo.all() if status is None or r.status == status]
        requests.sort(key=lambda r: r.created_at, reverse=True)
        return [public_view(r) for r in requests[:limit]]

    @app.get("/requests/{request_id}")
    def get_request(request_id: str, pack: str | None = None) -> dict[str, Any]:
        request = reg(pack).repo.get(request_id)
        if request is None:
            raise HTTPException(404, "request not found")
        return public_view(request)

    @app.get("/track/{request_id}")
    def track(request_id: str) -> dict[str, Any]:
        """Citizen-facing lookup by tracking ID across all packs: status, category and where it was filed."""
        found = []
        for pack_id in c().pack_ids:
            request = c().region(pack_id).repo.get(request_id)
            if request is not None:
                found.append((pack_id, request))
        if not found:
            raise HTTPException(404, "no request with that tracking ID")
        # most specific first: the pilot copy (district level) if the request fell inside one, then the country copy
        found.sort(key=lambda f: c().config(f[0]).get("level") != "region")
        pack_id, request = found[0]
        where = list(dict.fromkeys(r.geo.district for _, r in found if r.geo.district))
        return public_view(request) | {"pack": pack_id, "country_name": c().config(pack_id).get("country_name"), "where": where}

    # --- rankings --------------------------------------------------------------------------------

    @app.get("/rankings")
    def rankings(
        pack: str | None = None,
        preset: str = "balanced",
        demand: float | None = Query(None, ge=0),
        need: float | None = Query(None, ge=0),
        equity: float | None = Query(None, ge=0),
        alignment: float | None = Query(None, ge=0),
        urgency: float | None = Query(None, ge=0),
        sector: str | None = None,
        admin_code: str | None = None,
        limit: int = Query(20, ge=1, le=5000),
        sensitivity: bool = True,
    ) -> dict[str, Any]:
        overrides = {"demand": demand, "need": need, "equity": equity, "alignment": alignment, "urgency": urgency}
        weights = resolve_weights(preset, overrides)
        items = reg(pack).demand.rankings(weights, sector=sector, admin_code=admin_code, limit=limit, sensitivity=sensitivity)
        return {"preset": preset, "weights": weights.as_dict() if weights else None, "items": items}

    @app.get("/rankings/compare")
    def compare(pack: str | None = None, a: str = VOLUME_ONLY, b: str = "equity_first", k: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
        for preset in (a, b):
            if preset != VOLUME_ONLY and preset not in PRESETS:
                raise HTTPException(422, f"unknown preset {preset!r}")
        return reg(pack).demand.compare(a, b, k)

    @app.get("/clusters/{cluster_id}")
    def cluster(cluster_id: str, pack: str | None = None, preset: str = "balanced") -> dict[str, Any]:
        weights = resolve_weights(preset, {}) or PRESETS["balanced"]
        view = reg(pack).demand.cluster(cluster_id, weights)
        if view is None:
            raise HTTPException(404, "cluster not found")
        return view

    @app.post("/clusters/{cluster_id}/status", dependencies=[require_admin])
    def set_cluster_status(cluster_id: str, body: StatusIn, pack: str | None = None) -> dict[str, Any]:
        """Officials move a whole cluster along (forwarded, in progress, resolved). Every request in it, and its
        copies in the country's other packs, get the new status, so citizens see it when they track their ID.
        Resolved requests leave the ranking."""
        region = reg(pack)
        requests = region.demand.cluster_requests(cluster_id)
        if not requests:
            raise HTTPException(404, "cluster not found")
        ids = {r.id for r in requests}
        updated = 0
        for pack_id in c().packs_for_country(region.ctx.country):
            other = c().region(pack_id)
            copies = [r for i in ids if (r := other.repo.get(i)) is not None]
            if copies:
                other.repo.add_many(r.model_copy(update={"status": body.status}) for r in copies)
                other.demand.invalidate()
                updated += len(copies) if pack_id == region.ctx.pack_id else 0
        return {"cluster_id": cluster_id, "status": body.status, "n_requests": updated}

    @app.get("/districts")
    def districts(pack: str | None = None) -> list[dict[str, Any]]:
        return reg(pack).demand.districts()

    @app.get("/districts/silent")
    def silent_districts(pack: str | None = None, k: int = Query(5, ge=1, le=50)) -> list[dict[str, Any]]:
        return reg(pack).demand.silent_districts(k)

    # --- open data export (DPG indicator 6) ------------------------------------------------------

    @app.get("/export/aggregates.csv")
    def export_csv(pack: str | None = None, level: str = Query("district", pattern="^(district|h3)$")) -> Response:
        region = reg(pack)
        rows, suppressed = region.demand.aggregates(level, settings.export_min_requesters)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=AGGREGATE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            buffer.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="aggregates_{region.ctx.pack_id}_{level}.csv"',
                "X-Suppressed-Groups": str(suppressed),
            },
        )

    @app.get("/export/aggregates.geojson")
    def export_geojson(pack: str | None = None, level: str = Query("district", pattern="^(district|h3)$")) -> dict[str, Any]:
        import h3

        rows, suppressed = reg(pack).demand.aggregates(level, settings.export_min_requesters)
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
            country = country_for_number(message.sender_id)
            if country and not container_.packs_for_country(country):
                country = None
            request = container_.ingest.ingest(
                channel="whatsapp", sender_id=message.sender_id, text=message.text,
                audio=audio, audio_mime=mime, lat=message.lat, lon=message.lon, country=country,
            )
            if container_.whatsapp:
                container_.whatsapp.send_text(message.reply_to, ack_message(request, local_language(container_, country)))
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
            # Telegram gives no phone number, so the default pack's country is assumed.
            request = container_.ingest.ingest(
                channel="telegram", sender_id=message.sender_id, text=message.text,
                audio=audio, audio_mime=message.media_mime, lat=message.lat, lon=message.lon,
            )
            if bot:
                bot.send_text(message.reply_to, ack_message(request, local_language(container_)))
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
