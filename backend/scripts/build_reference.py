"""Build the per-pack reference files from open sources: unit list, boundaries and populated places.

    python -m scripts.build_reference --pack all       # needs network the first time (~300 MB, cached)

For each pack it writes, under data/reference/<PACK>/:
  units.csv            code, names, aliases, population, centroid, priority flag
  boundaries.geojson   simplified polygons (properties: admin_code, name, name_local)
  settlements.csv      the most populated places per unit, used by the synthetic generator

Sources (pinned):
  boundaries  geoBoundaries gbOpen, release 9469f09 (licence varies by country, see data/LICENSE-DATA.md)
  population  Kontur Population 2023-11-01, H3 resolution 6 (CC BY 4.0), summed inside each polygon.
              Maharashtra keeps its Census 2011 figures.
  Alagoas     IBGE localities API for the official municipality list and codes; Census 2022 population
              (small municipalities next to Maceió get far too much from a 3 km grid)

Needs shapely (requirements-dev.txt); the API itself does not.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import shutil
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import h3
import httpx
import numpy as np
import shapely
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from app.config import REPO_ROOT
from scripts import _regions as R

GB_URL = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/{iso}/{level}/geoBoundaries-{iso}-{level}_simplified.geojson"
KONTUR_URL = "https://geodata-eu-central-1-kontur-public.s3.eu-central-1.amazonaws.com/kontur_datasets/kontur_population_20231101_r6.gpkg.gz"
IBGE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
IBGE_POP_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/4709/periodos/2022/variaveis/93?localidades=N6%5BN3%5B{uf}%5D%5D"
IBGE_POP_SOURCE = "IBGE Censo Demográfico 2022, table 4709 (resident population)"
KONTUR_SOURCE = "Kontur Population 2023-11-01 (H3 r6, CC BY 4.0), summed inside geoBoundaries polygons"
UNIT_FIELDS = ["admin_code", "district_name", "name_local", "alt_names", "weak_names", "official_code", "population",
               "population_year", "population_source", "population_verified", "centroid_lat", "centroid_lon",
               "aspirational", "notes"]
N_SETTLEMENTS = 6
PILOT_CHILD_RES = 8  # pilots spread each r6 cell over its r8 children so small municipalities get a share


@dataclass
class PackSpec:
    pack_id: str
    iso3: str
    level: str  # ADM1 (country pack) or ADM2 (pilot)
    tolerance: float  # simplification, degrees
    units: list = field(default_factory=list)  # [(Unit, source keys)]
    match: str = "iso"  # iso | name
    parent_iso: str | None = None  # pilots: ISO 3166-2 code of the ADM1 feature that contains the units
    parent_name: str | None = None  # pilots whose ADM1 layer has no ISO codes (China)


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold().replace("’", "'")


def download(url: str, dest: Path) -> Path:
    if dest.is_file():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=600) as response:
        response.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)
    tmp.replace(dest)
    return dest


def geoboundaries(cache: Path, iso3: str, level: str) -> list[dict]:
    path = download(GB_URL.format(iso=iso3, level=level), cache / f"gb-{iso3}-{level}.geojson")
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def kontur(cache: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    gpkg = cache / "kontur_population_20231101_r6.gpkg"
    if not gpkg.is_file():
        gz = download(KONTUR_URL, cache / "kontur_population_20231101_r6.gpkg.gz")
        with gzip.open(gz, "rb") as src, gpkg.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    rows = sqlite3.connect(gpkg).execute("select h3, population from population").fetchall()
    cells = [r[0] for r in rows]
    latlng = np.array([h3.cell_to_latlng(c) for c in cells])
    return latlng[:, 0], latlng[:, 1], np.array([r[1] for r in rows], dtype=float), cells


def spec_list(pack_ids: list[str]) -> list[PackSpec]:
    def pilot(units):
        return [(unit, names) for unit, names in units]

    specs = [
        PackSpec("BR", "BRA", "ADM1", 0.02, [(unit, [unit[0]]) for unit in R.BR_STATES]),
        PackSpec("RU", "RUS", "ADM1", 0.05, [(unit, [unit[0]]) for unit in R.RU_SUBJECTS]),
        PackSpec("IN", "IND", "ADM1", 0.01, [(unit, [unit[0]]) for unit in R.IN_STATES]),
        PackSpec("CN", "CHN", "ADM1", 0.02, [(unit, [name]) for unit, name in R.CN_PROVINCES], match="name"),
        PackSpec("ZA", "ZAF", "ADM1", 0.01, [(unit, [code]) for unit, code in R.ZA_PROVINCES]),
        PackSpec("BR-AL", "BRA", "ADM2", 0.002, match="name", parent_iso="BR-AL"),  # units filled from IBGE
        PackSpec("RU-TY", "RUS", "ADM2", 0.005, pilot(R.RU_TY_UNITS), match="name", parent_iso="RU-TY"),
        PackSpec("CN-NX", "CHN", "ADM2", 0.003, pilot(R.CN_NX_UNITS), match="name",
                 parent_name="Ningxia Ningxia Hui Autonomous Region"),
        PackSpec("ZA-EC", "ZAF", "ADM2", 0.003, pilot(R.ZA_EC_UNITS), match="name", parent_iso="EC"),
        PackSpec("IN-MH", "IND", "ADM2", 0.003, match="name", parent_iso="IN-MH"),  # units from the existing file
    ]
    wanted = {s.pack_id for s in specs} if pack_ids == ["all"] else set(pack_ids)
    unknown = wanted - {s.pack_id for s in specs}
    if unknown:
        raise SystemExit(f"unknown pack(s): {sorted(unknown)}")
    return [s for s in specs if s.pack_id in wanted]


def alagoas_units(cache: Path) -> tuple[list, dict[str, str], dict[str, int]]:
    path = download(IBGE_URL.format(uf=27), cache / "ibge-municipios-27.json")
    census = json.loads(download(IBGE_POP_URL.format(uf=27), cache / "ibge-pop2022-27.json").read_text(encoding="utf-8"))
    by_ibge = {s["localidade"]["id"]: int(s["serie"]["2022"]) for s in census[0]["resultados"][0]["series"]}
    units, codes, pop = [], {}, {}
    for m in sorted(json.loads(path.read_text(encoding="utf-8")), key=lambda m: m["nome"]):
        name = m["nome"]
        slug = fold(name).upper().replace("'", "").replace(" ", "_").replace("-", "_")
        weak = name in R.BR_AL_WEAK
        unit = R.u(f"BR-AL-{slug}", name, name, "" if weak else fold(name) if fold(name) != name.casefold() else "",
                   f"{name};{fold(name)}" if weak else "")
        units.append((unit, [name]))
        codes[unit[0]] = str(m["id"])
        pop[unit[0]] = by_ibge[str(m["id"])]
    return units, codes, pop


def maharashtra_units(data_dir: Path) -> tuple[list, dict[str, dict]]:
    """Maharashtra keeps its existing reference rows (Census 2011 population, aspirational flags)."""
    path = next(p for p in (data_dir / "reference" / "IN-MH" / "units.csv", data_dir / "reference" / "districts_IN-MH.csv") if p.is_file())
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = {r["admin_code"]: r for r in csv.DictReader(fh)}
    by_name = {v: k for k, v in R.IN_MH_SOURCE_NAMES.items()}
    units = []
    for code, row in rows.items():
        unit = R.u(code, row["district_name"], row.get("name_local", ""), row.get("alt_names", ""), row.get("weak_names", ""),
                   row.get("aspirational", "").lower() == "true")
        units.append((unit, [by_name.get(code, row["district_name"])]))
    return units, rows


def select_features(spec: PackSpec, features: list[dict], parent) -> dict[str, list]:
    """Source geometries per unit code."""
    key = (lambda f: f["properties"].get("shapeISO", "")) if spec.match == "iso" else (lambda f: fold(f["properties"].get("shapeName") or ""))
    wanted = {fold(k) if spec.match == "name" else k: unit[0] for unit, keys in spec.units for k in keys}
    candidates: dict[str, list[tuple[float, object]]] = defaultdict(list)
    for feature in features:
        code = wanted.get(key(feature))
        if code is None:
            continue
        geom = shape(feature["geometry"]).buffer(0)
        overlap = geom.intersection(parent).area / geom.area if parent is not None else 1.0
        candidates[code].append((overlap, geom))
    out: dict[str, list] = {}
    for code, found in candidates.items():
        # Same-named units elsewhere in the country overlap the parent by ~0. The ADM1 and ADM2 layers come from
        # different surveys, so a genuine border unit can overlap as little as 20%: then take the best match.
        keep = [g for o, g in found if o >= 0.3] or [g for o, g in sorted(found, key=lambda f: -f[0])[:1] if o > 0.1]
        if keep:
            out[code] = keep
    missing = [unit[0] for unit, _ in spec.units if unit[0] not in out]
    if missing:
        raise SystemExit(f"{spec.pack_id}: no boundary found for {missing}")
    return out


def build(spec: PackSpec, data_dir: Path, cache: Path, pop) -> None:
    print(f"{spec.pack_id}:")
    official: dict[str, str] = {}
    census: dict[str, int] = {}
    mh_rows: dict[str, dict] = {}
    if spec.pack_id == "BR-AL":
        spec.units, official, census = alagoas_units(cache)
    elif spec.pack_id == "IN-MH":
        spec.units, mh_rows = maharashtra_units(data_dir)

    parent = None
    if spec.level == "ADM2":
        for f in geoboundaries(cache, spec.iso3, "ADM1"):
            props = f["properties"]
            if (spec.parent_iso and props.get("shapeISO") == spec.parent_iso) or (spec.parent_name and props.get("shapeName") == spec.parent_name):
                parent = shape(f["geometry"]).buffer(0)
    geoms = {code: unary_union(parts) for code, parts in select_features(spec, geoboundaries(cache, spec.iso3, spec.level), parent).items()}

    # population: count each r6 cell (or its r8 children, for pilots) whose centre falls inside a unit
    lat, lon, value, cells = pop

    def points(bounds, children: bool):
        minx, miny, maxx, maxy = bounds
        idx = np.nonzero((lon >= minx - .2) & (lon <= maxx + .2) & (lat >= miny - .2) & (lat <= maxy + .2))[0]
        if not children:
            return lat[idx], lon[idx], value[idx], [cells[i] for i in idx]
        pts = []
        for i in idx:
            kids = h3.cell_to_children(cells[i], PILOT_CHILD_RES)
            pts.extend((*h3.cell_to_latlng(k), value[i] / len(kids), cells[i]) for k in kids)
        return (np.array([q[0] for q in pts]), np.array([q[1] for q in pts]), np.array([q[2] for q in pts]),
                [q[3] for q in pts])

    all_points = points(unary_union(list(geoms.values())).bounds, spec.level == "ADM2")
    population: dict[str, float] = {}
    places: dict[str, list[tuple[float, float, float]]] = {}
    centroid: dict[str, tuple[float, float]] = {}
    for code, geom in geoms.items():
        p_lat, p_lon, p_val, p_cell = all_points
        inside = shapely.contains_xy(geom, p_lon, p_lat)
        if not inside.any():  # small islands: every r6 centre is at sea, so spread cells over their children
            p_lat, p_lon, p_val, p_cell = points(geom.bounds, True)
            inside = shapely.contains_xy(geom, p_lon, p_lat)
        population[code] = float(p_val[inside].sum())
        groups: dict[str, list[int]] = defaultdict(list)
        for j in np.nonzero(inside)[0]:
            groups[p_cell[j]].append(j)
        ranked = sorted(groups.values(), key=lambda js: -p_val[js].sum())[:N_SETTLEMENTS]
        places[code] = [(float(p_lat[js].mean()), float(p_lon[js].mean()), float(p_val[js].sum())) for js in ranked]
        weighted = None
        if population[code] > 0:
            w = p_val[inside]
            weighted = shapely.Point(float((p_lon[inside] * w).sum() / w.sum()), float((p_lat[inside] * w).sum() / w.sum()))
        point = weighted if weighted is not None and geom.contains(weighted) else geom.representative_point()
        centroid[code] = (point.y, point.x)

    out_dir = data_dir / "reference" / spec.pack_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for unit, _ in spec.units:
        code, name, local, aliases, weak, priority = unit
        row = {
            "admin_code": code, "district_name": name, "name_local": local, "alt_names": ";".join(aliases),
            "weak_names": ";".join(weak), "official_code": official.get(code, ""),
            "population": str(round(population[code])), "population_year": "2023", "population_source": KONTUR_SOURCE,
            "population_verified": "false", "centroid_lat": f"{centroid[code][0]:.4f}", "centroid_lon": f"{centroid[code][1]:.4f}",
            "aspirational": str(priority).lower(), "notes": "",
        }
        if code in census:
            row.update({"population": str(census[code]), "population_year": "2022", "population_source": IBGE_POP_SOURCE,
                        "population_verified": "true"})
        if code in mh_rows:  # keep curated Census values and centroids
            old = mh_rows[code]
            row.update({
                "official_code": old.get("official_code") or old.get("lgd_code", ""),
                "population": old.get("population") or old["population_2011"], "population_year": "2011",
                "population_source": old.get("population_source") or "Census of India 2011",
                "population_verified": old.get("population_verified", "false"),
                "centroid_lat": old["centroid_lat"], "centroid_lon": old["centroid_lon"], "notes": old.get("notes", ""),
            })
        rows.append(row)
    with (out_dir / "units.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=UNIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    digits = 4 if spec.level == "ADM2" else 3
    features = []
    for unit, _ in spec.units:
        geom = shapely.set_precision(geoms[unit[0]].simplify(spec.tolerance, preserve_topology=True), 10 ** -digits)
        features.append({"type": "Feature", "properties": {"admin_code": unit[0], "name": unit[1], "name_local": unit[2]},
                         "geometry": mapping(geom)})
    (out_dir / "boundaries.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                                           ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    with (out_dir / "settlements.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["admin_code", "lat", "lon", "population"])
        for unit, _ in spec.units:
            for p_lat_, p_lon_, p_pop in places[unit[0]]:
                writer.writerow([unit[0], f"{p_lat_:.4f}", f"{p_lon_:.4f}", round(p_pop)])

    total = sum(int(r["population"]) for r in rows)
    size = (out_dir / "boundaries.geojson").stat().st_size // 1024
    print(f"  {len(rows)} units, population {total / 1e6:.1f} M, boundaries {size} KB -> {out_dir.relative_to(REPO_ROOT)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", nargs="+", default=["all"])
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--cache", type=Path, default=REPO_ROOT / "data" / "cache")
    args = parser.parse_args(argv)
    specs = spec_list(args.pack)
    print("loading Kontur population grid...")
    pop = kontur(args.cache)
    for spec in specs:
        build(spec, args.data_dir, args.cache, pop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
