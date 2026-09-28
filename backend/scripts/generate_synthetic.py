"""Generate a labelled synthetic request dataset for demos and tests. Every record has synthetic=true.

Built-in stories:
- Volume is skewed toward big, well-connected districts, so a volume-only ranking favours them (the equity story).
- Poorer districts send few requests (the "silent districts" panel).
- One brigading attack is planted: 200 near-identical messages from 12 numbers in 30 minutes (the integrity story).

Also writes a placeholder data/processed/planned_projects.csv unless data/raw/planned_projects.csv exists.

    python -m scripts.generate_synthetic --n 1200 --seed 42
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
from app.pack import PackContext, load_pack, read_pack_config
from app.privacy import hash_requester
from app.taxonomy import SECTORS
from scripts._templates import (
    BRIGADE_SUFFIXES, BRIGADE_TEXT, BRIGADE_TEXT_EN, CLOSERS, DISTRICT_ONLY, LANDMARKS, OPENERS, TEMPLATES,
)

IST = timezone(timedelta(hours=5, minutes=30))
SYNTHETIC_SALT = "synthetic-dataset"
SCORED_SECTORS = [s for s in SECTORS if s != "other"]
# How much more likely a resident is to file digitally. Assumption for the demo skew, not data.
CONNECTIVITY = {
    "IN-MH-MUMBAI_CITY": 4.0, "IN-MH-MUMBAI_SUBURBAN": 4.0, "IN-MH-PUNE": 3.5, "IN-MH-THANE": 3.0,
    "IN-MH-NAGPUR": 2.5, "IN-MH-NASHIK": 1.8, "IN-MH-AURANGABAD": 1.8, "IN-MH-KOLHAPUR": 1.5,
}
LANG_MIX_URBAN = {"mr": 0.25, "hi": 0.20, "hi-Latn": 0.30, "en": 0.25}
LANG_MIX_RURAL = {"mr": 0.45, "hi": 0.25, "hi-Latn": 0.20, "en": 0.10}
CHANNEL_MIX = {"whatsapp": 0.70, "web": 0.20, "telegram": 0.10}
TIER_MIX = {"A": 0.60, "B": 0.25, "C": 0.15}
HOTSPOT_WEIGHTS = [5, 3, 2, 1, 1]
WINDOW_DAYS = 45


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
    parts.append(rng.choice(CLOSERS[lang]))
    return " ".join(p for p in parts if p), " ".join(p for p in parts_en if p), urgency


def allocate(n: int, weights: dict[str, float], minimum: int = 2) -> dict[str, int]:
    total = sum(weights.values())
    return {code: max(minimum, round(n * w / total)) for code, w in weights.items()}


def organic_requests(ctx: PackContext, rng: random.Random, n: int, as_of: datetime) -> list[CivicRequest]:
    poverty = {c: d.poverty for c, d in ctx.districts.items()}
    lo, hi = min(poverty.values()), max(poverty.values())
    poverty_norm = {c: (v - lo) / (hi - lo) if hi > lo else 0.5 for c, v in poverty.items()}
    weights = {c: d.population * CONNECTIVITY.get(c, 1.0) * (1.4 - poverty_norm[c]) for c, d in ctx.districts.items()}
    counts = allocate(n, weights)

    records: list[CivicRequest] = []
    for code in sorted(counts):
        district, info = ctx.districts[code], ctx.info[code]
        need_weights = [0.2 + district.need.get(s, 0.0) for s in SCORED_SECTORS]
        # Low-volume (mostly rural) districts: requests concentrate in a couple of villages around one issue.
        n_hotspots = 2 if counts[code] < 15 else 3 if counts[code] < 40 else len(HOTSPOT_WEIGHTS)
        hotspot_weights = HOTSPOT_WEIGHTS[:n_hotspots]
        hotspots = [
            (info.lat + rng.gauss(0, 0.12), info.lon + rng.gauss(0, 0.12), rng.choices(SCORED_SECTORS, weights=need_weights)[0])
            for _ in hotspot_weights
        ]
        pool = [f"syn-{code}-{i}" for i in range(max(3, int(counts[code] * 0.85)))]
        urban = CONNECTIVITY.get(code, 1.0) >= 2.0
        for _ in range(counts[code]):
            h_lat, h_lon, dominant = rng.choices(hotspots, weights=hotspot_weights)[0]
            sector = dominant if rng.random() < 0.75 else rng.choices(SCORED_SECTORS, weights=need_weights)[0]
            lang = pick(rng, LANG_MIX_URBAN if urban else LANG_MIX_RURAL)
            tier = pick(rng, TIER_MIX)
            label = info.name if lang in ("en", "hi-Latn") else info.name_local
            if tier == "A":
                lat, lon, method, place = h_lat + rng.gauss(0, 0.004), h_lon + rng.gauss(0, 0.004), "gps", None
            elif tier == "B":
                landmark, landmark_en = rng.choice(LANDMARKS[lang])
                lat, lon, method = h_lat + rng.gauss(0, 0.006), h_lon + rng.gauss(0, 0.006), "geocode"
                place = (f"{landmark}, {label}", f"{landmark_en}, {info.name}")
            else:
                lat = lon = None
                method = "gazetteer"
                place = (DISTRICT_ONLY[lang].format(d=label), f"({info.name} district)")
            text, text_en, urgency = compose(rng, lang, sector, place)
            channel = pick(rng, CHANNEL_MIX)
            records.append(
                CivicRequest(
                    id=f"syn-{len(records):05d}",
                    channel=channel,
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


def brigade_requests(ctx: PackContext, rng: random.Random, code: str, as_of: datetime, start_index: int) -> tuple[list[CivicRequest], dict]:
    info = ctx.info[code]
    lat, lon = info.lat + 0.031, info.lon - 0.047
    start = as_of - timedelta(days=3, hours=5)
    senders = [f"brigade-{i}" for i in range(12)]
    records = []
    for i in range(200):
        p_lat, p_lon = lat + rng.gauss(0, 0.0008), lon + rng.gauss(0, 0.0008)
        records.append(
            CivicRequest(
                id=f"syn-{start_index + i:05d}",
                channel="whatsapp",
                lang="hi-Latn",
                code_mixed=True,
                text_original=BRIGADE_TEXT + rng.choice(BRIGADE_SUFFIXES),
                text_en=BRIGADE_TEXT_EN,
                category="roads",
                urgency="high",
                summary_redacted=BRIGADE_TEXT_EN,
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
                "budget_inr_lakh": str(rng.randint(50, 2000)),
                "status": status,
                "source": "SYNTHETIC placeholder - replace with state budget / PM Gati Shakti extracts",
                "synthetic": "true",
            })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", default="IN-MH")
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--n", type=int, default=1200, help="approximate number of organic requests")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", default="2026-09-28", help="end of the 45-day window (IST date)")
    parser.add_argument("--brigade-district", default="IN-MH-PUNE")
    parser.add_argument("--no-brigade", action="store_true")
    args = parser.parse_args(argv)

    data_dir: Path = args.data_dir
    config = read_pack_config(data_dir, args.pack)
    raw_planned = data_dir / "raw" / "planned_projects.csv"
    planned_path = data_dir / config["files"]["planned_projects"]
    rng = random.Random(args.seed)

    if not raw_planned.is_file():
        ctx = load_pack(data_dir, args.pack)
        rows = placeholder_projects(ctx, random.Random(f"{args.seed}:projects"))
        planned_path.parent.mkdir(parents=True, exist_ok=True)
        with planned_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} placeholder planned projects -> {planned_path.relative_to(REPO_ROOT)}")

    ctx = load_pack(data_dir, args.pack)
    as_of = datetime.fromisoformat(args.as_of).replace(hour=18, tzinfo=IST)
    records = organic_requests(ctx, rng, args.n, as_of)
    brigade_meta = None
    if not args.no_brigade:
        attack, brigade_meta = brigade_requests(ctx, rng, args.brigade_district, as_of, len(records))
        records += attack

    out_dir = data_dir / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "requests.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        fh.writelines(r.model_dump_json() + "\n" for r in records)

    by_district: dict[str, int] = {}
    for r in records:
        by_district[r.geo.district] = by_district.get(r.geo.district, 0) + 1
    manifest = {
        "generator": "scripts/generate_synthetic.py",
        "licence": "CC-BY-4.0",
        "pack": args.pack,
        "seed": args.seed,
        "as_of": as_of.isoformat(),
        "window_days": WINDOW_DAYS,
        "n_records": len(records),
        "n_organic": len(records) - (brigade_meta["n_messages"] if brigade_meta else 0),
        "brigade": brigade_meta,
        "records_by_district": dict(sorted(by_district.items(), key=lambda kv: -kv[1])),
        "assumptions": {"connectivity": CONNECTIVITY, "lang_mix_urban": LANG_MIX_URBAN, "lang_mix_rural": LANG_MIX_RURAL,
                        "location_tiers": TIER_MIX, "channels": CHANNEL_MIX},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(records)} synthetic requests -> {out_path.relative_to(REPO_ROOT)}")
    if brigade_meta:
        print(f"planted brigade: {brigade_meta['n_messages']} messages / {brigade_meta['n_senders']} senders -> {brigade_meta['main_cluster_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
