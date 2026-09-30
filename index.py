"""Vercel entrypoint: exposes the FastAPI app from backend/ at the repository root.

Vercel runs this file as a Python function with the whole repository around it, so the pages (frontend/) and the
region data (data/) are deployed too. Locally, use start.bat / start.ps1 instead.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import app  # noqa: E402,F401  (Vercel looks for a variable named `app`)
