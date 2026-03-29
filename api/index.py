import os
import sys
import traceback

# Make the project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from temporalos.api.main import app  # noqa: E402
except Exception:
    # If the real app fails to import, create a diagnostic app that
    # returns the traceback so we can see what's actually broken.
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    _tb = traceback.format_exc()

    app = FastAPI()

    @app.get("/{path:path}")
    async def diagnostic(path: str = "") -> PlainTextResponse:
        return PlainTextResponse(
            f"DealFrame failed to start.\n\n{_tb}",
            status_code=500,
        )
