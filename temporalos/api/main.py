"""FastAPI application entry point."""
# © 2024-2026 Phani Marupaka. All rights reserved.
# DealFrame — Video → Structured Negotiation Intelligence Engine
# Author: Phani Marupaka <https://linkedin.com/in/phani-marupaka>

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from ..config import get_settings
from ..db.session import init_db
from ..observability.telemetry import setup_telemetry

logger = logging.getLogger(__name__)
from .routes import (
    finetuning, intelligence, local, metrics, observatory, process, search, stream,
)
from .routes import (
    agents, batch, clips, diarization, integrations, schemas, summaries, webhooks,
)
from .routes import auth as auth_routes
from .routes import export as export_routes
from .routes import notifications as notification_routes
from .routes import seed as seed_routes
from .routes import (
    active_learning as al_routes,
    admin as admin_routes,
    annotations as annotation_routes,
    audit as audit_routes,
    copilot as copilot_routes,
    diff as diff_routes,
    patterns as pattern_routes,
)
from .routes import chat as chat_routes
from .routes import progress as progress_routes
from .routes import flywheel as flywheel_routes
from .routes import share as share_routes
from .routes import deals as deals_routes
from .routes import live_copilot as live_copilot_routes
from .routes import verticals as verticals_routes
from .routes import uploads as uploads_routes

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    import logging
    _log = logging.getLogger(__name__)

    # ── Telemetry (non-fatal) ──────────────────────────────────────────────
    try:
        settings = get_settings()
        setup_telemetry(
            service_name=settings.telemetry.service_name,
            otlp_endpoint=settings.telemetry.otlp_endpoint,
            enabled=settings.telemetry.enabled,
        )
    except Exception as exc:
        _log.warning("Telemetry init skipped: %s", exc)

    # ── Database (non-fatal — app runs in degraded mode without DB) ───────
    try:
        await init_db()
    except Exception as exc:
        _log.warning("Database init failed (app will run without persistence): %s", exc)

    # ── Initialize DB persistence for all services ─────────────────────────
    try:
        from ..db.session import get_session_factory
        sf = get_session_factory()
        if sf:
            from ..enterprise.audit import init_audit_trail
            from ..notifications import init_notification_service
            from ..intelligence.annotations import init_annotation_store
            from ..intelligence.active_learning import init_active_learning_queue
            from ..auth import init_auth, load_users_from_db
            from ..enterprise.multi_tenant import init_tenant_persistence, load_tenants_from_db

            # Init services with session factory
            audit = init_audit_trail(sf)
            notif_svc = init_notification_service(sf)
            ann_store = init_annotation_store(sf)
            al_queue = init_active_learning_queue(session_factory=sf)
            init_auth(session_factory=sf, secret_key=settings.auth_secret)
            init_tenant_persistence(sf)

            # Load existing data from DB into memory
            await audit.load_from_db()
            await notif_svc.load_from_db()
            await ann_store.load_from_db()
            await al_queue.load_from_db()
            await load_users_from_db()
            await load_tenants_from_db()

            # Restore job queue + rebuild search index from DB
            from .routes.process import load_jobs_from_db
            await load_jobs_from_db()
            await _rebuild_search_index_from_db(sf)
    except Exception as exc:
        _log.warning("Service init skipped: %s", exc)

    # ── Durable DB-backed job worker (in-process, no Redis) ────────────────
    _worker_started = False
    try:
        from ..batch.durable_queue import start_worker
        start_worker()
        _worker_started = True
        _log.info("Durable job worker started")
    except Exception as exc:
        _log.warning("Durable worker skipped: %s", exc)

    # ── Auto-seed demo data if database is empty ────────────────────────────
    try:
        from .routes.process import _jobs
        if len(_jobs) == 0:
            _log.info("No jobs in database — auto-seeding demo data…")
            from .routes.seed import seed_demo_data
            result = await seed_demo_data()
            _log.info("Auto-seeded %d videos (%d segments)",
                       result["videos_created"], result["total_segments"])
    except Exception as exc:
        _log.warning("Auto-seed skipped: %s", exc)

    # ── Seed YouTube demo data + agents ────────────────────────────────────
    from .routes.process import _jobs
    if len(_jobs) == 0:
        # No jobs at all — generate from scratch into cache + DB + agents
        try:
            from scripts.seed_youtube_demo import seed_all as yt_seed_all
            stats = await yt_seed_all()
            logger.info("Auto-seeded YouTube demo: %s", stats)
        except Exception as exc:
            logger.warning("YouTube auto-seed skipped: %s", exc)
    else:
        # Jobs exist (loaded from DB) — seed agents from cached jobs
        try:
            from scripts.seed_youtube_demo import (
                generate_youtube_seed, seed_agents, seed_search_index,
            )
            data = generate_youtube_seed()
            # Only seed agents for jobs that are in the cache
            agent_stats = seed_agents(data)
            search_count = seed_search_index(data)
            logger.info(
                "Seeded agents from %d cached jobs: QA=%d risk=%d KG=%d search=%d",
                len(_jobs), agent_stats["qa_indexed"],
                agent_stats["risk_alerts"], agent_stats["kg_entities"],
                search_count,
            )
        except Exception as exc:
            logger.warning("Agent seed from cache skipped: %s", exc)

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    if _worker_started:
        try:
            from ..batch.durable_queue import stop_worker
            await stop_worker()
        except Exception:  # pragma: no cover
            pass


async def _rebuild_search_index_from_db(session_factory) -> None:
    """Rebuild the in-memory search index from persisted SearchDocRecords."""
    try:
        from ..db.models import SearchDocRecord
        from ..search.indexer import IndexEntry, get_search_index
        from sqlalchemy import select

        idx = get_search_index()
        async with session_factory() as sess:
            rows = (await sess.execute(select(SearchDocRecord))).scalars().all()
            for row in rows:
                entry = IndexEntry(
                    doc_id=row.id,
                    video_id=row.video_id,
                    timestamp_ms=row.timestamp_ms,
                    timestamp_str="",
                    topic=row.topic or "",
                    risk=row.risk or "",
                    risk_score=row.risk_score or 0.0,
                    objections=row.objections or [],
                    decision_signals=row.decision_signals or [],
                    transcript=row.transcript or "",
                    model=row.model or "",
                )
                idx.index(entry)
        import logging
        logging.getLogger(__name__).info(
            "Rebuilt search index with %d documents", len(rows))
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to rebuild search index: %s", exc)


app = FastAPI(
    title="DealFrame",
    description="Video → Structured Procurement & Negotiation Intelligence Engine",
    version="0.1.0",
    lifespan=lifespan,
)

FastAPIInstrumentor.instrument_app(app)

# ── Copyright attribution middleware ─────────────────────────────────────────
# Embedded in every HTTP response header — do not remove.
_AUTHOR = "Phani Marupaka"
_COPYRIGHT = "(c) 2024-2026 Phani Marupaka. All rights reserved."

class _AttributionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Powered-By"] = "DealFrame"
        response.headers["X-Author"] = _AUTHOR
        response.headers["X-Copyright"] = _COPYRIGHT
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: wss:; "
            "font-src 'self'; "
            "frame-ancestors 'none'"
        )
        return response

class _TenantGuardMiddleware(BaseHTTPMiddleware):
    """Enforces tenant presence on /api/v1/* when DEALFRAME_REQUIRE_TENANT=1.

    Keeps the /share/view/* and /ws/* paths open so public share links and
    WebSocket streams continue to work. Unauthenticated requests get 401.
    """

    _SKIP_PREFIXES = ("/api/v1/share/view", "/api/v1/deals", "/api/v1/metrics", "/api/v1/health")

    async def dispatch(self, request: Request, call_next) -> Response:
        import os as _os
        from fastapi.responses import JSONResponse

        path = request.url.path
        enforce = _os.environ.get("DEALFRAME_REQUIRE_TENANT", "").lower() in {"1", "true", "yes"}
        if enforce and path.startswith("/api/v1/") and not any(path.startswith(p) for p in self._SKIP_PREFIXES):
            tenant_id = request.headers.get("x-tenant-id") or request.headers.get("X-Tenant-ID")
            if not tenant_id:
                try:
                    from ..enterprise.multi_tenant import get_tenant
                    ctx = get_tenant()
                    tenant_id = ctx.tenant_id if ctx is not None else None
                except Exception:
                    tenant_id = None
            if not tenant_id:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "tenant required — supply X-Tenant-ID header"},
                )
            request.state.tenant_id = tenant_id
        return await call_next(request)


app.add_middleware(_AttributionMiddleware)
app.add_middleware(_TenantGuardMiddleware)

app.include_router(process.router, prefix="/api/v1")
app.include_router(observatory.router, prefix="/api/v1")
app.include_router(intelligence.router, prefix="/api/v1")
app.include_router(finetuning.router, prefix="/api/v1")
app.include_router(local.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(stream.router)  # WebSocket at /ws/stream (no /api/v1 prefix)

# New platform capability routes
app.include_router(diarization.router, prefix="/api/v1")
app.include_router(summaries.router, prefix="/api/v1")
app.include_router(clips.router, prefix="/api/v1")
app.include_router(schemas.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(batch.router, prefix="/api/v1")
app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(export_routes.router, prefix="/api/v1")
app.include_router(notification_routes.router, prefix="/api/v1")

# Phase J: Frontend-facing routes for Phase G/H backend modules
app.include_router(annotation_routes.router, prefix="/api/v1")
app.include_router(al_routes.router, prefix="/api/v1")
app.include_router(audit_routes.router, prefix="/api/v1")
app.include_router(diff_routes.router, prefix="/api/v1")
app.include_router(pattern_routes.router, prefix="/api/v1")
app.include_router(copilot_routes.router, prefix="/api/v1")
app.include_router(admin_routes.router, prefix="/api/v1")
app.include_router(seed_routes.router, prefix="/api/v1")

# Wave 1 — Chat-with-Deal, SSE progress
app.include_router(chat_routes.router, prefix="/api/v1")
app.include_router(progress_routes.router, prefix="/api/v1")

# Wave 2 — Fine-tuning flywheel, Deal inbox, Export/Share
app.include_router(flywheel_routes.router, prefix="/api/v1")
app.include_router(share_routes.router, prefix="/api/v1")
app.include_router(deals_routes.router, prefix="/api/v1")

# Wave 3 — Live negotiation copilot (WebSocket mic + cue cards)
app.include_router(live_copilot_routes.router)
app.include_router(verticals_routes.router, prefix="/api/v1")
app.include_router(uploads_routes.router, prefix="/api/v1")


# ── Seed endpoint ──────────────────────────────────────────────────────────
@app.post("/api/v1/seed/youtube", tags=["seed"])
async def seed_youtube_demo() -> dict:
    """Seed demo data from YouTube videos. Idempotent — safe to call multiple times."""
    from scripts.seed_youtube_demo import seed_all as yt_seed_all
    stats = await yt_seed_all()
    return {"status": "seeded", **stats}


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "service": "temporalos", "version": "0.1.0"}


@app.get("/health/live", tags=["meta"])
async def liveness() -> dict:
    """Kubernetes liveness probe — is the process alive?"""
    return {"status": "alive"}


@app.get("/health/ready", tags=["meta"])
async def readiness() -> dict:
    """Kubernetes readiness probe — can the service accept traffic?"""
    from .routes.process import _jobs
    db_ok = False
    try:
        from ..db.session import get_session_factory
        sf = get_session_factory()
        if sf:
            async with sf() as sess:
                await sess.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {
        "status": "ready" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "jobs_in_memory": len(_jobs),
    }


# ── Serve compiled React frontend ─────────────────────────────────────────────
# Mount /assets only when the dist directory exists (after `npm run build`)
_assets_dir = _FRONTEND_DIST / "assets"
if _assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str) -> FileResponse:
    """SPA catch-all — serve index.html for any non-API path."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    index = _FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    # Frontend not built yet — return a hint via JSON if no HTML
    raise HTTPException(
        status_code=503,
        detail="Frontend not built. Run: cd frontend && npm run build",
    )
