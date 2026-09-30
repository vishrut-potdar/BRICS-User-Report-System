"""Loads a country/state pack: district reference, indicators, planned projects and optional boundaries.

A pack is config, not code: supporting another BRICS region means adding files under data/, not editing this.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .scoring import DistrictContext
from .taxonomy import SECTORS

FUNDED_STATUSES = frozenset({"funded", "sanctioned", "in_progress", "completed"})
DELAYED_STATUSES = frozenset({"delayed", "stalled"})

Ring = list[tuple[float, float]]  # (lon, lat) pairs, GeoJSON order
Polygon = list[Ring]  # outer ring first, then holes


@dataclass(frozen=True)
class DistrictInfo:
    admin_code: str
    name: str
    name_local: str
    aliases: tuple[str, ...]
    lat: float
    lon: float
    lgd_code: str = ""  # official code: LGD (India), IBGE (Brazil)...
    population_verified: bool = False
    weak_aliases: tuple[str, ...] = ()  # also ordinary words; matched only in place mentions, never free text


@dataclass
class PackContext:
    pack_id: str
    country: str
    region_name: str
    h3_resolution: int
    languages: tuple[str, ...]
    districts: dict[str, DistrictContext]
    info: dict[str, DistrictInfo]
    planned: dict[tuple[str, str], str] = field(default_factory=dict)
    boundaries: dict[str, list[Polygon]] = field(default_factory=dict)
    placeholder_metrics: dict[str, tuple[str, ...]] = field(default_factory=dict)
    synthetic_planned: bool = False
    country_name: str = ""
    level: str = "region"  # country: units are states/provinces; region: units are districts of one state
    parent: str | None = None  # the country pack a region pack sits under
    unit_label: str = "district"
    unit_label_plural: str = "districts"
    priority_label: str | None = None  # what the equity bonus flag means here, e.g. "Aspirational District"
    boundaries_path: Path | None = None

    @property
    def synthetic_indicators(self) -> bool:
        return any(self.placeholder_metrics.values())


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_pack_config(data_dir: Path, pack_id: str) -> dict[str, Any]:
    return json.loads((data_dir / "packs" / f"{pack_id}.json").read_text(encoding="utf-8"))


def district_infos(data_dir: Path, config: dict[str, Any]) -> dict[str, DistrictInfo]:
    infos = {}
    for row in read_csv(data_dir / config["files"]["district_reference"]):
        weak = {n.strip() for n in (row.get("weak_names") or "").split(";") if n.strip()}
        names = [row["district_name"], row.get("name_local", ""), *(row.get("alt_names") or "").split(";")]
        infos[row["admin_code"]] = DistrictInfo(
            admin_code=row["admin_code"],
            name=row["district_name"],
            name_local=row.get("name_local", "") or row["district_name"],
            aliases=tuple(dict.fromkeys(n.strip() for n in names if n.strip() and n.strip() not in weak)),
            lat=float(row["centroid_lat"]),
            lon=float(row["centroid_lon"]),
            lgd_code=row.get("official_code") or row.get("lgd_code", ""),
            population_verified=truthy(row.get("population_verified")),
            weak_aliases=tuple(sorted(weak)),
        )
    return infos


def _load_planned(path: Path) -> tuple[dict[tuple[str, str], str], bool]:
    """Collapse project rows to one status per (district, sector): funded beats delayed beats none."""
    if not path.is_file():
        return {}, False
    planned: dict[tuple[str, str], str] = {}
    synthetic = False
    for row in read_csv(path):
        status = row["status"].strip().lower()
        key = (row["admin_code"], row["sector"])
        synthetic |= truthy(row.get("synthetic"))
        if status in FUNDED_STATUSES:
            planned[key] = "funded"
        elif status in DELAYED_STATUSES and planned.get(key) != "funded":
            planned[key] = "delayed"
    return planned, synthetic


def _load_boundaries(path: Path) -> dict[str, list[Polygon]]:
    if not path.is_file():
        return {}
    boundaries: dict[str, list[Polygon]] = {}
    for feature in json.loads(path.read_text(encoding="utf-8")).get("features", []):
        code = (feature.get("properties") or {}).get("admin_code")
        geometry = feature.get("geometry") or {}
        if not code:
            continue
        if geometry.get("type") == "Polygon":
            polygons = [geometry["coordinates"]]
        elif geometry.get("type") == "MultiPolygon":
            polygons = geometry["coordinates"]
        else:
            continue
        boundaries.setdefault(code, []).extend(
            [[[(float(pt[0]), float(pt[1])) for pt in ring] for ring in polygon] for polygon in polygons]
        )
    return boundaries


def unit_population(row: dict[str, str]) -> int:
    return int(float(row.get("population") or row.get("population_2011") or 0))


def available_packs(data_dir: Path) -> list[str]:
    """Packs whose indicator table has been built, in file-name order."""
    ids = []
    for path in sorted((data_dir / "packs").glob("*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        if (data_dir / config["files"]["indicators"]).is_file():
            ids.append(config["pack_id"])
    return ids


def load_pack(data_dir: Path, pack_id: str) -> PackContext:
    config = read_pack_config(data_dir, pack_id)
    files = config["files"]
    indicators_path = data_dir / files["indicators"]
    if not indicators_path.is_file():
        raise FileNotFoundError(
            f"{indicators_path} not found. From backend/, run: python -m scripts.build_indicators --allow-placeholder"
        )
    infos = district_infos(data_dir, config)
    districts: dict[str, DistrictContext] = {}
    placeholders: dict[str, tuple[str, ...]] = {}
    for row in read_csv(indicators_path):
        code = row["admin_code"]
        if code not in infos:
            continue
        districts[code] = DistrictContext(
            admin_code=code,
            name=infos[code].name,
            population=int(float(row["population"])),
            poverty=float(row["poverty"]),
            aspirational=truthy(row["aspirational"]),
            need={s: float(row[f"need_{s}"]) for s in SECTORS if row.get(f"need_{s}") not in (None, "")},
            synthetic=truthy(row.get("synthetic")),
        )
        placeholders[code] = tuple(m for m in (row.get("placeholder_metrics") or "").split(";") if m)

    planned, synthetic_planned = _load_planned(data_dir / files["planned_projects"]) if files.get("planned_projects") else ({}, False)
    boundaries_path = data_dir / files["boundaries_geojson"] if files.get("boundaries_geojson") else None
    boundaries = _load_boundaries(boundaries_path) if boundaries_path else {}
    return PackContext(
        pack_id=config["pack_id"],
        country=config["country"],
        region_name=config["region_name"],
        h3_resolution=int(config.get("h3_resolution", 7)),
        languages=tuple(config.get("languages", [])),
        districts=districts,
        info=infos,
        planned=planned,
        boundaries=boundaries,
        placeholder_metrics=placeholders,
        synthetic_planned=synthetic_planned,
        country_name=config.get("country_name", config["country"]),
        level=config.get("level", "region"),
        parent=config.get("parent"),
        unit_label=config.get("unit_label", "district"),
        unit_label_plural=config.get("unit_label_plural", "districts"),
        priority_label=config.get("priority_label"),
        boundaries_path=boundaries_path if boundaries_path and boundaries_path.is_file() else None,
    )
