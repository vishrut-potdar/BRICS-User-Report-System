"""Load each pack's synthetic requests into its repository (REPOSITORY=local|firestore).

    python -m scripts.seed --reset                  # demo reset: wipe, then load data/synthetic/<pack>/requests.jsonl
    python -m scripts.seed --pack BR BR-AL --reset  # only some packs
"""

from __future__ import annotations

import argparse

from app.config import get_settings
from app.container import build_repository
from app.models import CivicRequest
from app.pack import read_pack_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", nargs="+", default=["all"])
    parser.add_argument("--reset", action="store_true", help="delete everything in each pack's repository first")
    args = parser.parse_args(argv)

    settings = get_settings()
    data_dir = settings.data_dir
    packs = sorted(p.stem for p in (data_dir / "packs").glob("*.json")) if args.pack == ["all"] else args.pack
    for pack_id in packs:
        path = data_dir / read_pack_config(data_dir, pack_id)["files"]["synthetic_requests"]
        if not path.is_file():
            print(f"{pack_id}: skipped, {path} not found (run scripts.generate_synthetic)")
            continue
        repo = build_repository(settings, pack_id)
        if args.reset:
            repo.clear()
        with path.open(encoding="utf-8") as fh:
            count = repo.add_many(CivicRequest.model_validate_json(line) for line in fh if line.strip())
        target = settings.local_store_dir / pack_id if settings.repository == "local" else settings.repository
        print(f"{pack_id}: loaded {count} requests into {settings.repository} ({target})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
