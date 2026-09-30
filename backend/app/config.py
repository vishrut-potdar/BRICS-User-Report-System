"""Runtime settings, read from environment variables and an optional repo-root .env file."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_SALT = "dev-only-salt-change-me"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, `#` comments. Variables already set in the environment win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = REPO_ROOT / "data"
    pack_id: str = "IN"  # default pack: what /rankings etc. return without ?pack=, and the country for Telegram
    packs: tuple[str, ...] = ()  # packs to serve; empty = every pack in data/packs whose indicators are built
    language_provider: str = "offline"  # gemini | offline
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    repository: str = "local"  # local | memory | firestore
    local_store_dir: Path = REPO_ROOT / "data" / "store"  # one <dir>/<pack>/requests.jsonl per pack
    firestore_collection: str = "requests"  # one collection per pack: <name>_<pack>
    phone_hash_salt: str = DEV_SALT
    google_maps_api_key: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_graph_version: str = "v21.0"
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    export_min_requesters: int = 5
    cors_origins: tuple[str, ...] = ("*",)

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv(REPO_ROOT / ".env")
        env = lambda key, default=None: os.environ.get(key) or default  # noqa: E731 - empty string counts as unset
        gemini_key = env("GEMINI_API_KEY")
        settings = cls(
            data_dir=_path(env("DATA_DIR", "data")),
            pack_id=env("PACK_ID", "IN"),
            packs=tuple(p.strip() for p in env("PACKS", "").split(",") if p.strip()),
            language_provider=env("LANGUAGE_PROVIDER", "gemini" if gemini_key else "offline"),
            gemini_api_key=gemini_key,
            gemini_model=env("GEMINI_MODEL", cls.gemini_model),
            repository=env("REPOSITORY", "local"),
            local_store_dir=_path(env("LOCAL_STORE_DIR", "data/store")),
            firestore_collection=env("FIRESTORE_COLLECTION", "requests"),
            phone_hash_salt=env("PHONE_HASH_SALT", DEV_SALT),
            google_maps_api_key=env("GOOGLE_MAPS_API_KEY"),
            whatsapp_verify_token=env("WHATSAPP_VERIFY_TOKEN"),
            whatsapp_access_token=env("WHATSAPP_ACCESS_TOKEN"),
            whatsapp_phone_number_id=env("WHATSAPP_PHONE_NUMBER_ID"),
            whatsapp_app_secret=env("WHATSAPP_APP_SECRET"),
            whatsapp_graph_version=env("WHATSAPP_GRAPH_VERSION", cls.whatsapp_graph_version),
            telegram_bot_token=env("TELEGRAM_BOT_TOKEN"),
            telegram_webhook_secret=env("TELEGRAM_WEBHOOK_SECRET"),
            export_min_requesters=int(env("EXPORT_MIN_REQUESTERS", "5")),
            cors_origins=tuple(o.strip() for o in env("CORS_ORIGINS", "*").split(",") if o.strip()),
        )
        if settings.phone_hash_salt == DEV_SALT:
            warnings.warn("PHONE_HASH_SALT is not set; using the development salt", stacklevel=2)
        return settings


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
