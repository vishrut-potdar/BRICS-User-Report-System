"""Wires settings into concrete services. The API and the scripts both build from here.

One process serves every pack (country level and pilot regions). Each pack is a Region with its own
reference data, repository and read-side cache. Packs load lazily on first use.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .channels.telegram import TelegramClient
from .channels.whatsapp import WhatsAppClient
from .config import Settings
from .geo import GeoResolver
from .ingest import IngestService
from .language import LanguageProvider, build_provider
from .pack import PackContext, available_packs, load_pack, read_pack_config
from .repository import FirestoreRepository, LocalRepository, RequestRepository
from .service import DemandService


class UnknownPack(KeyError):
    pass


@dataclass
class Region:
    ctx: PackContext
    repo: RequestRepository
    resolver: GeoResolver
    demand: DemandService


def build_repository(settings: Settings, pack_id: str) -> RequestRepository:
    if settings.repository == "memory":
        return LocalRepository(None)
    if settings.repository == "local":
        return LocalRepository(settings.local_store_dir / pack_id / "requests.jsonl")
    if settings.repository == "firestore":
        return FirestoreRepository(f"{settings.firestore_collection}_{pack_id}")
    raise RuntimeError(f"unknown REPOSITORY {settings.repository!r}")


@dataclass
class Container:
    settings: Settings
    pack_ids: tuple[str, ...]
    whatsapp: WhatsAppClient | None
    telegram: TelegramClient | None
    _regions: dict[str, Region] = field(default_factory=dict)
    _providers: dict[str, LanguageProvider] = field(default_factory=dict)
    _configs: dict[str, dict] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    # --- packs -------------------------------------------------------------------------------------

    def config(self, pack_id: str) -> dict:
        if pack_id not in self.pack_ids:
            raise UnknownPack(pack_id)
        if pack_id not in self._configs:
            self._configs[pack_id] = read_pack_config(self.settings.data_dir, pack_id)
        return self._configs[pack_id]

    def region(self, pack_id: str | None = None) -> Region:
        pack_id = pack_id or self.settings.pack_id
        with self._lock:
            if pack_id not in self._regions:
                self.config(pack_id)  # raises UnknownPack
                ctx = load_pack(self.settings.data_dir, pack_id)
                repo = build_repository(self.settings, pack_id)
                self._regions[pack_id] = Region(
                    ctx=ctx,
                    repo=repo,
                    resolver=GeoResolver(ctx, maps_api_key=self.settings.google_maps_api_key),
                    demand=DemandService(repo, ctx),
                )
            return self._regions[pack_id]

    def packs_for_country(self, country: str) -> list[str]:
        """Country pack first, then its regions."""
        ids = [p for p in self.pack_ids if self.config(p)["country"] == country]
        return sorted(ids, key=lambda p: (self.config(p).get("level") != "country", p))

    def country_of(self, pack_id: str) -> str:
        return self.config(pack_id)["country"]

    def provider_for(self, country: str) -> LanguageProvider:
        with self._lock:
            if country not in self._providers:
                config = self.config(self.packs_for_country(country)[0])
                self._providers[country] = build_provider(
                    self.settings, config.get("country_name", country), tuple(config.get("languages", []))
                )
            return self._providers[country]

    # --- the default pack, for scripts and single-region callers ------------------------------------

    @property
    def ctx(self) -> PackContext:
        return self.region().ctx

    @property
    def repo(self) -> RequestRepository:
        return self.region().repo

    @property
    def demand(self) -> DemandService:
        return self.region().demand

    @property
    def resolver(self) -> GeoResolver:
        return self.region().resolver

    @property
    def provider(self) -> LanguageProvider:
        return self.provider_for(self.country_of(self.settings.pack_id))

    @property
    def ingest(self) -> IngestService:
        return IngestService(self, self.settings.phone_hash_salt)


def build_container(settings: Settings) -> Container:
    found = available_packs(settings.data_dir)
    pack_ids = tuple(p for p in (settings.packs or found) if p in found)
    missing = [p for p in settings.packs if p not in found]
    if missing or settings.pack_id not in pack_ids:
        raise FileNotFoundError(
            f"pack(s) {missing or [settings.pack_id]} not built. From backend/, run: "
            "python -m scripts.build_indicators --pack all --allow-placeholder"
        )
    whatsapp = (
        WhatsAppClient(settings.whatsapp_access_token, settings.whatsapp_phone_number_id, settings.whatsapp_graph_version)
        if settings.whatsapp_access_token and settings.whatsapp_phone_number_id
        else None
    )
    telegram = TelegramClient(settings.telegram_bot_token) if settings.telegram_bot_token else None
    return Container(settings=settings, pack_ids=pack_ids, whatsapp=whatsapp, telegram=telegram)
