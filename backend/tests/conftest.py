"""A tiny three-district pack so tests never depend on generated data files."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h3
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.container import build_container
from app.main import create_app
from app.models import CivicRequest, Geo
from app.taxonomy import SECTORS

# code, name, local name, population, lat, lon, aspirational, poverty, need (all sectors)
DISTRICTS = [
    ("TS-PUNE", "Pune", "पुणे", 5_000_000, 18.52, 73.86, False, 0.05, 0.10),
    ("TS-AURANGABAD", "Aurangabad", "औरंगाबाद", 2_000_000, 19.88, 75.34, False, 0.15, 0.40),
    ("TS-NANDURBAR", "Nandurbar", "नंदुरबार", 1_000_000, 21.37, 74.24, True, 0.35, 0.70),
]
T0 = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    for sub in ("packs", "reference", "processed"):
        (tmp_path / sub).mkdir()
    pack = {
        "pack_id": "TS", "country": "IN", "region_name": "Testland", "h3_resolution": 7, "languages": ["mr", "hi", "en"],
        "files": {
            "district_reference": "reference/districts.csv",
            "indicators": "processed/district_indicators.csv",
            "planned_projects": "processed/planned_projects.csv",
        },
    }
    (tmp_path / "packs" / "TS.json").write_text(json.dumps(pack), encoding="utf-8")
    _write_csv(tmp_path / "reference" / "districts.csv", [
        {"admin_code": c, "district_name": n, "name_local": l, "alt_names": "", "lgd_code": "", "population_2011": p,
         "population_verified": "false", "centroid_lat": la, "centroid_lon": lo, "aspirational": str(a).lower()}
        for c, n, l, p, la, lo, a, _, _ in DISTRICTS
    ])
    _write_csv(tmp_path / "processed" / "district_indicators.csv", [
        {"admin_code": c, "district_name": n, "population": p, "poverty": pov, "aspirational": str(a).lower(),
         **{f"need_{s}": need for s in SECTORS}, "placeholder_metrics": "", "synthetic": "false"}
        for c, n, _, p, _, _, a, pov, need in DISTRICTS
    ])
    _write_csv(tmp_path / "processed" / "planned_projects.csv", [
        {"project_id": "P1", "admin_code": "TS-PUNE", "sector": "water", "name": "x", "budget_inr_lakh": "1",
         "status": "funded", "source": "test", "synthetic": "true"},
        {"project_id": "P2", "admin_code": "TS-AURANGABAD", "sector": "water", "name": "y", "budget_inr_lakh": "1",
         "status": "delayed", "source": "test", "synthetic": "true"},
    ])
    return tmp_path


@pytest.fixture
def settings(data_dir: Path) -> Settings:
    return Settings(data_dir=data_dir, pack_id="TS", language_provider="offline", repository="memory",
                    phone_hash_salt="test-salt", export_min_requesters=5)


@pytest.fixture
def container(settings: Settings):
    return build_container(settings)


@pytest.fixture
def client(settings: Settings, container) -> TestClient:
    return TestClient(create_app(settings, container))


def make_requests(admin_code: str, lat: float, lon: float, *, n: int, requesters: int, sector: str = "water",
                  urgent: int = 0, text: str | None = None, spread: timedelta = timedelta(days=20),
                  prefix: str = "r") -> list[CivicRequest]:
    cell = h3.latlng_to_cell(lat, lon, 7)
    return [
        CivicRequest(
            id=f"{prefix}-{admin_code}-{sector}-{i}",
            channel="web",
            lang="en",
            text_original=text or f"Issue report number {i} about {sector}: details vary {i * 7919 % 1000}",
            text_en="x",
            category=sector,
            urgency="high" if i < urgent else "low",
            summary_redacted=f"summary {i}",
            geo=Geo(lat=lat, lon=lon, h3=cell, admin_code=admin_code, district=admin_code, confidence="A", method="gps"),
            requester_hash=f"{prefix}-req-{i % requesters}",
            created_at=T0 + spread * (i / max(n, 1)),
            synthetic=True,
        )
        for i in range(n)
    ]
