"""Wires settings into concrete services. The API and the scripts both build from here."""

from __future__ import annotations

from dataclasses import dataclass

from .channels.telegram import TelegramClient
from .channels.whatsapp import WhatsAppClient
from .config import Settings
from .geo import GeoResolver
from .ingest import IngestService
from .language import LanguageProvider, build_provider
from .pack import PackContext, load_pack
from .repository import FirestoreRepository, LocalRepository, RequestRepository
from .service import DemandService


@dataclass
class Container:
    settings: Settings
    ctx: PackContext
    repo: RequestRepository
    provider: LanguageProvider
    resolver: GeoResolver
    ingest: IngestService
    demand: DemandService
    whatsapp: WhatsAppClient | None
    telegram: TelegramClient | None


def build_repository(settings: Settings) -> RequestRepository:
    if settings.repository == "memory":
        return LocalRepository(None)
    if settings.repository == "local":
        return LocalRepository(settings.local_store_path)
    if settings.repository == "firestore":
        return FirestoreRepository(settings.firestore_collection)
    raise RuntimeError(f"unknown REPOSITORY {settings.repository!r}")


def build_container(settings: Settings) -> Container:
    ctx = load_pack(settings.data_dir, settings.pack_id)
    repo = build_repository(settings)
    provider = build_provider(settings, ctx.region_name)
    resolver = GeoResolver(ctx, maps_api_key=settings.google_maps_api_key)
    whatsapp = (
        WhatsAppClient(settings.whatsapp_access_token, settings.whatsapp_phone_number_id, settings.whatsapp_graph_version)
        if settings.whatsapp_access_token and settings.whatsapp_phone_number_id
        else None
    )
    telegram = TelegramClient(settings.telegram_bot_token) if settings.telegram_bot_token else None
    return Container(
        settings=settings,
        ctx=ctx,
        repo=repo,
        provider=provider,
        resolver=resolver,
        ingest=IngestService(provider, resolver, repo, settings.phone_hash_salt),
        demand=DemandService(repo, ctx),
        whatsapp=whatsapp,
        telegram=telegram,
    )
