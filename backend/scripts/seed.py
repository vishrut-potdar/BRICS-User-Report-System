"""Load a JSONL request file into the configured repository (REPOSITORY=local|firestore).

    python -m scripts.seed --reset            # demo reset: wipe, then load data/synthetic/requests.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import REPO_ROOT, get_settings
from app.container import build_repository
from app.models import CivicRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, default=REPO_ROOT / "data" / "synthetic" / "requests.jsonl")
    parser.add_argument("--reset", action="store_true", help="delete everything in the repository first")
    args = parser.parse_args(argv)

    settings = get_settings()
    repo = build_repository(settings)
    if args.reset:
        repo.clear()
    with args.file.open(encoding="utf-8") as fh:
        requests = [CivicRequest.model_validate_json(line) for line in fh if line.strip()]
    count = repo.add_many(requests)
    target = settings.local_store_path if settings.repository == "local" else settings.repository
    print(f"loaded {count} requests into {settings.repository} ({target})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
