"""CLI entry point for the DealFrame server.

Registered as the ``dealframe`` console script in pyproject.toml.
Deployment platforms (Railway/nixpacks, Render, Fly.io) call this to
start the ASGI server when an ``app`` / ``dealframe`` script is found.

Usage:
    dealframe              # production (uses $PORT, defaults to 8000)
    dealframe --reload     # development
"""
from __future__ import annotations

import os
import sys


def start() -> None:
    """Start the DealFrame ASGI server via uvicorn."""
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    reload = "--reload" in sys.argv

    uvicorn.run(
        "temporalos.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    start()
