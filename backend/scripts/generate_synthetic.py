"""Generate a labelled synthetic request dataset per pack for demos and tests. Every record has synthetic=true.

Built-in stories:
- Volume is skewed toward big, well-connected units, so a volume-only ranking favours them (the equity story).
- Poorer units send few requests (the "silent districts" panel).
- One brigading attack is planted: 200 near-identical messages from 12 numbers in 30 minutes (the integrity story).

Requests cluster around each unit's most populated places (reference/<pack>/settlements.csv). Language mix,
connectivity and the brigade target come from the pack's "synthetic" config.

Also writes a placeholder processed/<pack>/planned_projects.csv unless data/raw/<pack>/planned_projects.csv exists.

    python -m scripts.generate_synthetic --pack all
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h3

from app.clustering import cluster_id_for
from app.config import REPO_ROOT
from app.models import CivicRequest, Geo
from app.pack import PackContext, load_pack, read_csv, read_pack_config
from app.privacy import hash_requester
from app.taxonomy import SECTORS
from scripts._templates import BRIGADE, BRIGADE_SUFFIXES, CLOSERS, DETAILS, DISTRICT_ONLY, LANDMARKS, OPENERS, TEMPLATES

SYNTHETIC_SALT = "synthetic-dataset"
SCORED_SECTORS = [s for s in SECTORS if s != "other"]
CHANNEL_MIX = {"whatsapp": 0.70, "web": 0.20, "telegram": 0.10}
TIER_MIX = {"A": 0.60, "B": 0.25, "C": 0.15}
HOTSPOT_WEIGHTS = [5, 3, 2, 1, 1]
WINDOW_DAYS = 45
LATIN_LABEL = {"en", "hi-Latn", "pt", "af", "zu", "xh"}  # languages that write the unit's English/Latin name
CURRENCY = {"IN": "INR", "BR": "BRL", "RU": "RUB", "CN": "CNY", "ZA": "ZAR"}


def pick(rng: random.Random, mix: dict[str, float]) -> str:
    return rng.choices(list(mix), weights=list(mix.values()))[0]


def compose(rng: random.Random, lang: str, sector: str, place: tuple[str, str] | None) -> tuple[str, str, str]:
    text, text_en, urgency = rng.choice(TEMPLATES[sector][lang])
    n = rng.randint(2, 12)
    body, body_en = text.format(n=n), (text_en or text).format(n=n)
    parts = [rng.choice(OPENERS[lang]), body]
    parts_en = [body_en]
    if place:
        parts.append(place[0])
        parts_en.append(place[1])
    details = DETAILS.get(lang, [])
    for detail, detail_en in rng.sample(details, k=min(len(details), rng.randint(1, 2))):
        parts.append(detail)
        parts_en.append(detail_en or detail)
    parts.append(rng.choice(CLOSERS[lang]))
    sep = "" if lang == "zh" else " "
    return sep.join(p for p in parts if p), " ".join(p for p in parts_en if p), urgency


def allocate(n: int, weights: dict[str, float], minimum: int = 2) -> dict[str, int]:
    total = sum(weights.values())
    return {code: max(minimum, round(n * w / total)) for code, w in weights.items()}


def settlements(data_dir: Path, config: dict) -> dict[str, list[tuple[float, float, float]]]:
    path = data_dir / config["files"].get("settlements", "")
    places: dict[str, list[tuple[float, float, float]]] = {}
    if path.is_file():
        for row in read_csv(path):
            places.setdefault(row["admin_code"], []).append((float(row["lat"]), float(row["lon"]), float(row["population"])))
    return places


def organic_requests(ctx: PackContext, config: dict, places: dict, rng: random.Random, n: int, as_of: datetime) -> list[CivicRequest]:
    syn = config.get("synthetic", {})
    connectivity: dict[str, float] = syn.get("connectivity", {})
    mix_rural: dict[str, float] = syn.get("lang_mix", {"en": 1.0})
    mix_urban: dict[str, float] = syn.get("lang_mix_urban", mix_rural)
    mix_by_unit: dict[str, dict[str, float]] = syn.get("lang_mix_by_unit", {})
    spread = 0.03 if ctx.level == "region" else 0.08

    poverty = {c: d.poverty for c, d in ctx.districts.items()}
    lo, hi = min(poverty.values()), max(poverty.values())
    poverty_norm = {c: (v - lo) / (hi - lo) if hi > lo else 0.5 for c, v in poverty.items()}
    weights = {c: d.population * connectivity.get(c, 1.0) * (1.4 - poverty_norm[c]) for c, d in ctx.districts.items() if d.population > 0}
    counts = allocate(n, weights)

    records: list[CivicRequest] = []
    for code in sorted(counts):
        district, info = ctx.districts[code], ctx.info[code]
        need_weights = [0.2 + district.need.get(s, 0.0) for s in SCORED_SECTORS]
        # Low-volume (mostly rural) units: requests concentrate in a couple of places around one issue.
        n_hotspots = 2 if counts[code] < 15 else 3 if counts[code] < 40 else len(HOTSPOT_WEIGHTS)
        hotspot_weights = HOTSPOT_WEIGHTS[:n_hotspots]
        anchors = places.get(code) or [(info.lat, info.lon, 1.0)]
        hotspots = []
        for i in range(n_hotspots):
            a_lat, a_lon, _ = anchors[i % len(anchors)]
            hotspots.append((a_lat + rng.gauss(0, spread), a_lon + rng.gauss(0, spread),
                             rng.choices(SCORED_SECTORS, weights=need_weights)[0]))
        pool = [f"syn-{code}-{i}" for i in range(max(3, int(counts[code] * 0.85)))]
        urban = connectivity.get(code, 1.0) >= 2.0
        lang_mix = mix_by_unit.get(code) or (mix_urban if urban else mix_rural)
        for _ in range(counts[code]):
            h_lat, h_lon, dominant = rng.choices(hotspots, weights=hotspot_weights)[0]
            sector = dominant if rng.random() < 0.75 else rng.choices(SCORED_SECTORS, weights=need_weights)[0]
            lang = pick(rng, lang_mix)
            tier = pick(rng, TIER_MIX)
            label = info.name if lang in LATIN_LABEL else info.name_local
            if tier == "A":
                lat, lon, method, place = h_lat + rng.gauss(0, 0.004), h_lon + rng.gauss(0, 0.004), "gps", None
            elif tier == "B":
                landmark, landmark_en = rng.choice(LANDMARKS[lang])
                lat, lon, method = h_lat + rng.gauss(0, 0.006), h_lon + rng.gauss(0, 0.006), "geocode"
                place = (f"{landmark}, {label}", f"{landmark_en}, {info.name}")
            else:
                lat = lon = None
                method = "gazetteer"
                place = (DISTRICT_ONLY[lang].format(d=label), f"({info.name})")
            text, text_en, urgency = compose(rng, lang, sector, place)
            records.append(
                CivicRequest(
                    id=f"syn-{ctx.pack_id}-{len(records):05d}",
                    channel=pick(rng, CHANNEL_MIX),
                    lang=lang,
                    code_mixed=lang == "hi-Latn",
                    text_original=text,
                    text_en=text_en,
                    category=sector,
                    urgency=urgency,
                    summary_redacted=text_en,
                    geo=Geo(
                        lat=lat, lon=lon,
                        h3=h3.latlng_to_cell(lat, lon, ctx.h3_resolution) if lat is not None else None,
                        admin_code=code, district=info.name, location_text=place[0] if place else None,
                        confidence=tier, method=method,
                    ),
                    requester_hash=hash_requester("synthetic", rng.choice(pool), SYNTHETIC_SALT),
                    created_at=as_of - timedelta(seconds=rng.uniform(0, WINDOW_DAYS * 86400)),
                    provider="synthetic",
                    synthetic=True,
                )
            )
    return records


def brigade_requests(ctx: PackContext, places: dict, rng: random.Random, code: str, lang: str, as_of: datetime,
                     start_index: int) -> tuple[list[CivicRequest], dict]:
    info = ctx.info[code]
    anchor = (places.get(code) or [(info.lat, info.lon, 1.0)])[0]
    lat, lon = anchor[0] + 0.01, anchor[1] - 0.01
    text, text_en = BRIGADE[lang]
    start = as_of - timedelta(days=3, hours=5)
    senders = [f"brigade-{i}" for i in range(12)]
    records = []
    for i in range(200):
        p_lat, p_lon = lat + rng.gauss(0, 0.0008), lon + rng.gauss(0, 0.0008)
        records.append(
            CivicRequest(
                id=f"syn-{ctx.pack_id}-{start_index + i:05d}",
                channel="whatsapp",
                lang=lang,
                code_mixed=lang == "hi-Latn",
                text_original=text + rng.choice(BRIGADE_SUFFIXES),
                text_en=text_en,
                category="roads",
                urgency="high",
                summary_redacted=text_en,
                geo=Geo(lat=p_lat, lon=p_lon, h3=h3.latlng_to_cell(p_lat, p_lon, ctx.h3_resolution),
                        admin_code=code, district=info.name, confidence="A", method="gps"),
                requester_hash=hash_requester("synthetic", rng.choice(senders), SYNTHETIC_SALT),
                created_at=start + timedelta(seconds=rng.uniform(0, 30 * 60 - 1)),
                provider="synthetic",
                synthetic=True,
            )
        )
    cells = {r.geo.h3 for r in records}
    main_cell = max(cells, key=lambda c: sum(r.geo.h3 == c for r in records))
    meta = {
        "admin_code": code,
        "district": info.name,
        "sector": "roads",
        "lang": lang,
        "n_messages": len(records),
        "n_senders": len(senders),
        "window_start": start.isoformat(),
        "window_minutes": 30,
        "h3_cells": sorted(cells),
        "main_cluster_id": cluster_id_for(code, "roads", main_cell),
    }
    return records, meta


def placeholder_projects(ctx: PackContext, rng: random.Random) -> list[dict[str, str]]:
    rows = []
    for code in sorted(ctx.districts):
        for sector in SCORED_SECTORS:
            roll = rng.random()
            if roll >= 0.35:
                continue
            status = "funded" if roll < 0.20 else "delayed"
            rows.append({
                "project_id": f"PP-{code}-{sector}",
                "admin_code": code,
                "sector": sector,
                "name": f"{sector.title()} works, {ctx.info[code].name} (synthetic)",
                "budget_m": str(rng.randint(5, 200)),
                "currency": CURRENCY.get(ctx.country, ""),
                "status": status,
                "source": "SYNTHETIC placeholder - replace with state budget / national infrastructure pipeline extracts",
                "synthetic": "true",
            })
    return rows


def generate(data_dir: Path, pack_id: str, seed: int, as_of_date: str, n: int | None, brigade: bool) -> None:
    config = read_pack_config(data_dir, pack_id)
    syn = config.get("synthetic", {})
    raw_planned = data_dir / "raw" / pack_id / "planned_projects.csv"
    planned_path = data_dir / config["files"]["planned_projects"]
    rng = random.Random(f"{seed}:{pack_id}")

    if not raw_planned.is_file():
        ctx = load_pack(data_dir, pack_id)
        rows = placeholder_projects(ctx, random.Random(f"{seed}:{pack_id}:projects"))
        planned_path.parent.mkdir(parents=True, exist_ok=True)
        with planned_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    ctx = load_pack(data_dir, pack_id)
    places = settlements(data_dir, config)
    hours, _, minutes = config.get("utc_offset", "+00:00").lstrip("+-").partition(":")
    sign = -1 if config.get("utc_offset", "+").startswith("-") else 1
    tz = timezone(sign * timedelta(hours=int(hours), minutes=int(minutes or 0)))
    as_of = datetime.fromisoformat(as_of_date).replace(hour=18, tzinfo=tz)
    records = organic_requests(ctx, config, places, rng, n or int(syn.get("n", 1000)), as_of)
    brigade_meta = None
    target = syn.get("brigade")
    if brigade and target:
        attack, brigade_meta = brigade_requests(ctx, places, rng, target["admin_code"], target["lang"], as_of, len(records))
        records += attack

    out_path = data_dir / config["files"]["synthetic_requests"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.writelines(r.model_dump_json() + "\n" for r in records)

    by_district: dict[str, int] = {}
    for r in records:
        by_district[r.geo.district] = by_district.get(r.geo.district, 0) + 1
    manifest = {
        "generator": "scripts/generate_synthetic.py",
        "licence": "CC-BY-4.0",
        "pack": pack_id,
        "seed": seed,
        "as_of": as_of.isoformat(),
        "window_days": WINDOW_DAYS,
        "n_records": len(records),
        "n_organic": len(records) - (brigade_meta["n_messages"] if brigade_meta else 0),
        "brigade": brigade_meta,
        "records_by_district": dict(sorted(by_district.items(), key=lambda kv: -kv[1])),
        "assumptions": {"synthetic_config": syn, "location_tiers": TIER_MIX, "channels": CHANNEL_MIX},
    }
    (out_path.parent / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    brig = f", brigade {brigade_meta['main_cluster_id']}" if brigade_meta else ""
    print(f"{pack_id}: {len(records)} synthetic requests -> {out_path.relative_to(REPO_ROOT)}{brig}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", nargs="+", default=["all"])
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--n", type=int, default=None, help="approximate number of organic requests (default: pack config)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", default="2026-09-28", help="end of the 45-day window (local date)")
    parser.add_argument("--no-brigade", action="store_true")
    args = parser.parse_args(argv)

    data_dir: Path = args.data_dir
    packs = sorted(p.stem for p in (data_dir / "packs").glob("*.json")) if args.pack == ["all"] else args.pack
    for pack_id in packs:
        generate(data_dir, pack_id, args.seed, args.as_of, args.n, not args.no_brigade)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
