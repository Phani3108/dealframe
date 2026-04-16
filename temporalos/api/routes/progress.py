"""SSE endpoint that relays job progress events from the in-process EventBus.

Also exposes a replay endpoint that pulls persisted JobEvent rows so a client
reconnecting mid-pipeline can catch up without losing history.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ...observability.event_bus import get_event_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/progress", tags=["progress"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/jobs/{job_id}/events")
async def job_events_replay(job_id: str, limit: int = Query(200, ge=1, le=2000)) -> dict:
    """Return persisted job events (newest-first slice, re-ordered chronologically)."""
    try:
        from ...db.session import get_session_factory
        sf = get_session_factory()
        if not sf:
            return {"events": []}
        from ...db.models import JobEvent
        from sqlalchemy import select
        async with sf() as sess:
            rows = (await sess.execute(
                select(JobEvent)
                .where(JobEvent.job_id == job_id)
                .order_by(JobEvent.id.asc())
                .limit(limit)
            )).scalars().all()
        return {
            "events": [
                {
                    "id": r.id, "stage": r.stage, "status": r.status,
                    "detail": r.detail, "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ],
        }
    except Exception as exc:
        logger.debug("replay failed: %s", exc)
        return {"events": []}


@router.get("/jobs/{job_id}/stream")
async def job_progress_stream(job_id: str) -> StreamingResponse:
    """Subscribe to live progress events for this job over SSE.

    The stream replays any persisted events first, then tails live ones.
    """
    bus = get_event_bus()
    topic = f"job:{job_id}"
    queue = bus.subscribe(topic)

    async def gen():
        try:
            # Replay first
            replay = await job_events_replay(job_id)
            for ev in replay["events"]:
                yield _sse(ev.get("stage", "info"), ev)

            # Send initial heartbeat so clients know we're live
            yield _sse("ready", {"topic": topic})

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                yield _sse(event.get("stage", "info"), event)
                if event.get("stage") in {"done", "failed"}:
                    # Give the client a breath then close cleanly.
                    await asyncio.sleep(0.05)
                    break
        finally:
            bus.unsubscribe(topic, queue)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
