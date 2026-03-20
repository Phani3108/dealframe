"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from ..config import get_settings
from ..db.session import init_db
from ..observability.telemetry import setup_telemetry
from .routes import intelligence, observatory, process


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_telemetry(
        service_name=settings.telemetry.service_name,
        otlp_endpoint=settings.telemetry.otlp_endpoint,
        enabled=settings.telemetry.enabled,
    )
    await init_db()
    yield


app = FastAPI(
    title="TemporalOS",
    description="Video → Structured Decision Intelligence Engine",
    version="0.1.0",
    lifespan=lifespan,
)

FastAPIInstrumentor.instrument_app(app)

app.include_router(process.router, prefix="/api/v1")
app.include_router(observatory.router, prefix="/api/v1")
app.include_router(intelligence.router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "service": "temporalos", "version": "0.1.0"}
