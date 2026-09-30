"""Deployment: the Vercel entrypoint serves pages and seeded demo data from the repository root, without disk writes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib

from app.config import REPO_ROOT

VERCEL_SMOKE = r"""
import json, os
from fastapi.testclient import TestClient
import index

client = TestClient(index.app)
out = {path: client.get(path).status_code for path in ["/", "/admin", "/app.css", "/map.js", "/packs", "/config"]}
out["health"] = client.get("/health").json()
out["ranked_in_maharashtra"] =len(client.get("/rankings", params={"pack": "IN-MH", "limit": 50}).json()["items"])
out["ingest"] = client.post("/ingest", json={"text": "No water for 5 days", "pack": "IN", "admin_code": "IN-MH-PUNE"}).status_code
print(json.dumps(out))
"""


def test_vercel_entrypoint_serves_pages_and_seeded_data():
    # a fresh process, as on Vercel: repository root as working directory, VERCEL=1, and none of the local .env
    # settings (REPOSITORY, keys) leaking in
    env = {k: v for k, v in os.environ.items() if not k.startswith(("REPOSITORY", "LOCAL_STORE", "SEED_"))}
    env.update({"VERCEL": "1", "REPOSITORY": "", "LANGUAGE_PROVIDER": "offline", "GEOCODER": "none", "GEMINI_API_KEY": ""})
    result = subprocess.run([sys.executable, "-c", VERCEL_SMOKE], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr[-2000:]
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert all(out[p] == 200 for p in ["/", "/admin", "/app.css", "/map.js", "/packs", "/config"]), out
    assert out["health"]["pages"] is True and out["health"]["data"] is True, out["health"]
    assert out["ranked_in_maharashtra"] > 0, "synthetic demo data should be preloaded on Vercel"
    assert out["ingest"] == 201


def test_vercel_defaults_to_memory_with_seeding(monkeypatch):
    from app.config import Settings

    for key in ("REPOSITORY", "SEED_SYNTHETIC"):
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("VERCEL", "1")
    settings = Settings.from_env()
    assert settings.repository == "memory" and settings.seed_synthetic is True


def test_pyproject_dependencies_match_requirements():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = [line.strip() for line in (REPO_ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.startswith(("#", "-"))]
    assert sorted(project["project"]["dependencies"]) == sorted(requirements)
    assert project["tool"]["vercel"]["entrypoint"] == "index:app"


def test_vercel_bundle_excludes_nothing_the_app_needs():
    config = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    excluded = config["functions"]["index.py"]["excludeFiles"]
    for needed in ("frontend", "data/packs", "data/reference", "data/processed", "data/synthetic", "backend/app"):
        assert needed not in excluded


def test_vercel_ignores_a_copied_local_store_setting(monkeypatch):
    """Copying .env into Vercel brings REPOSITORY=local; the read-only disk cannot hold it, so memory wins."""
    from app.config import Settings

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("REPOSITORY", "local")
    assert Settings.from_env().repository == "memory"
    monkeypatch.setenv("REPOSITORY", "firestore")
    assert Settings.from_env().repository == "firestore"
