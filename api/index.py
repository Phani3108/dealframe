"""Vercel serverless entrypoint for DealFrame.

Vercel's Python runtime scans api/index.py (and other api/*.py files)
for an ASGI/WSGI ``app`` object.  This file bootstraps sys.path so the
``temporalos`` package is importable from the project root, then
re-exports the FastAPI app object as ``app``.

Vercel routes all incoming HTTP requests here via vercel.json.
"""
from __future__ import annotations

import os
import sys

# Add the project root to sys.path so `temporalos` is importable.
# __file__ is <project_root>/api/index.py  →  dirname(dirname) = project root
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from temporalos.api.main import app  # noqa: E402

# Explicit assignment — Vercel's static scanner requires `app = <object>`
app = app  # noqa: PLW0127

__all__ = ["app"]
