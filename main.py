"""Root-level ASGI entrypoint — required by deployment platforms.

Platforms (Railway/nixpacks, Render, Fly.io, Replit) scan for a root-level
file that exposes a FastAPI ``app`` object.  This module adds the project
root to sys.path so the ``temporalos`` package is importable even when the
package is not yet pip-installed (e.g. during platform build-time scanning).

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000
    gunicorn main:app -k uvicorn.workers.UvicornWorker
    python main.py   (starts uvicorn directly)
"""
from __future__ import annotations

import os
import sys

# Ensure the project root is on sys.path so `temporalos` is importable
# both before and after `pip install -e .`
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from temporalos.api.main import app  # noqa: E402

# Explicit re-assignment so every static scanner sees `app = <object>`
app = app  # noqa: PLW0127

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )
