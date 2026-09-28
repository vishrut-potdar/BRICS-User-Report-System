"""Build the district indicator tables the scorer reads.

Inputs
  data/reference/districts_<pack>.csv       district list, population, centroids
  data/raw/<metric>.csv                     one file per metric in the pack (see data/raw/README.md)
  data/raw/planned_projects.csv (optional)  real planned/funded projects

Outputs
  data/processed/indicators_long.csv        one row per (district, metric) with year, source, licence, placeholder flag
  data/processed/district_indicators.csv    wide table: population, poverty, aspirational, need_<sector>
  data/processed/planned_projects.csv       copied from raw if present (else generate_synthetic writes a placeholder)

Districts with no real value for a metric fail the build, unless --allow-placeholder is passed. Placeholders
are deterministic, shaped by rough tiers in the pack config, and flagged everywhere downstream.

    python -m scripts.build_indicators --allow-placeholder
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
import sys
from pathlib import Path

from app.config import REPO_ROOT
from app.pack import district_infos, read_csv, read_pack_config, truthy
from app.taxonomy import SECTORS

TIER_LATENT = {"high": 0.75, "mid": 0.45, "low": 0.15}
LONG_FIELDS = ["admin_code", "district_name", "metric", "value", "year", "source", "licence", "placeholder"]
PLANNED_FIELDS = ["project_id", "admin_code", "sector", "name", "budget_inr_lakh", "status", "source", "synthetic"]


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def load_raw_metric(path: Path, name_index: dict[str, str]) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Returns {admin_code: row} and a list of unmatched district names."""
    values: dict[str, dict[str, str]] = {}
    unmatched = []
    for row in read_csv(path):
        key = (row.get("admin_code") or row.get("district_name") or "").strip()
        code = name_index.get(key.casefold())
        if code is None:
            unmatched.append(key)
            continue
        value = float(row["value"])
        if (row.get("unit") or "").strip().lower() == "percent":
            value /= 100
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{path.name}: {key} value {value} is outside 0-1 (add unit=percent if it is a percentage)")
        values[code] = {
            "value": f"{value:.4f}",
            "year": row.get("year", ""),
            "source": row.get("source", ""),
            "licence": row.get("licence", ""),
        }
    return values, unmatched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", default="IN-MH")
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--allow-placeholder", action="store_true", help="fill missing values with flagged placeholders")
    args = parser.parse_args(argv)

    data_dir: Path = args.data_dir
    config = read_pack_config(data_dir, args.pack)
    infos = district_infos(data_dir, config)
    reference = {row["admin_code"]: row for row in read_csv(data_dir / config["files"]["district_reference"])}

    name_index: dict[str, str] = {}
    for code, info in infos.items():
        name_index[code.casefold()] = code
        for alias in info.aliases:
            name_index[alias.casefold()] = code

    placeholder_cfg = config.get("placeholder", {})
    tiers = placeholder_cfg.get("deprivation_tiers", {})
    tier_of = {code: tier for tier, codes in tiers.items() for code in codes}
    latent = {}
    for code in infos:
        rng = random.Random(f"{args.pack}:{code}:latent")
        latent[code] = clamp01(TIER_LATENT[tier_of.get(code, "mid")] + rng.uniform(-0.1, 0.1))

    long_rows: list[dict[str, str]] = []
    values: dict[tuple[str, str], float] = {}
    placeholders: dict[str, list[str]] = {code: [] for code in infos}
    missing: list[str] = []
    report: list[str] = []

    for metric, spec in config["metrics"].items():
        raw_path = data_dir / "raw" / f"{metric}.csv"
        raw, unmatched = load_raw_metric(raw_path, name_index) if raw_path.is_file() else ({}, [])
        if unmatched:
            print(f"warning: {raw_path.name}: unmatched districts {unmatched}", file=sys.stderr)
        intercept, slope = placeholder_cfg.get("metrics", {}).get(metric, (0.5, 0.0))
        n_placeholder = 0
        for code, info in infos.items():
            if code in raw:
                row = raw[code]
                value, is_placeholder = float(row["value"]), False
                year, source, licence = row["year"], row["source"], row["licence"]
            elif args.allow_placeholder:
                rng = random.Random(f"{args.pack}:{code}:{metric}")
                value = round(clamp01(intercept + slope * latent[code] + rng.gauss(0, 0.03)), 4)
                is_placeholder = True
                year, source, licence = "", f"PLACEHOLDER - replace with {spec.get('expected_source', 'a real source')}", "n/a"
                placeholders[code].append(metric)
                n_placeholder += 1
            else:
                missing.append(f"{metric}:{info.name}")
                continue
            values[(code, metric)] = value
            long_rows.append({
                "admin_code": code, "district_name": info.name, "metric": metric, "value": f"{value:.4f}",
                "year": year, "source": source, "licence": licence, "placeholder": str(is_placeholder).lower(),
            })
        report.append(f"  {metric:<28} real={len(infos) - n_placeholder:>3}  placeholder={n_placeholder:>3}")

    if missing:
        print(f"error: {len(missing)} missing values (first: {missing[:5]}). Add data/raw files or pass --allow-placeholder.", file=sys.stderr)
        return 1

    equity_metric = config["equity_metric"]
    wide_rows = []
    for code, info in infos.items():
        ref = reference[code]
        row = {
            "admin_code": code,
            "district_name": info.name,
            "population": ref["population_2011"],
            "poverty": f"{values[(code, equity_metric)]:.4f}",
            "aspirational": str(truthy(ref.get("aspirational"))).lower(),
        }
        for sector in SECTORS:
            mapping = config["need"][sector]
            raw_value = values[(code, mapping["metric"])]
            row[f"need_{sector}"] = f"{(1 - raw_value if mapping.get('invert') else raw_value):.4f}"
        row["placeholder_metrics"] = ";".join(placeholders[code])
        row["synthetic"] = str(bool(placeholders[code])).lower()
        wide_rows.append(row)

    out_dir = data_dir / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / config["files"]["indicators_long"]).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LONG_FIELDS)
        writer.writeheader()
        writer.writerows(long_rows)
    with (data_dir / config["files"]["indicators"]).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(wide_rows[0]))
        writer.writeheader()
        writer.writerows(wide_rows)

    raw_planned = data_dir / "raw" / "planned_projects.csv"
    if raw_planned.is_file():
        planned_rows = read_csv(raw_planned)
        header = set(planned_rows[0]) if planned_rows else set()
        if not set(PLANNED_FIELDS) - {"synthetic"} <= header:
            print(f"error: {raw_planned} needs columns {PLANNED_FIELDS}", file=sys.stderr)
            return 1
        shutil.copyfile(raw_planned, data_dir / config["files"]["planned_projects"])
        report.append("  planned_projects: copied from data/raw")

    print(f"Built indicators for {len(infos)} districts ({args.pack}):")
    print("\n".join(report))
    if any(placeholders.values()):
        print("NOTE: placeholder values are in use; they are flagged in the outputs and in the API (/meta, /districts).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
