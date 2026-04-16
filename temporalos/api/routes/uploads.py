"""Direct-to-storage presigned upload routes for large videos.

Protocol:
    1. Client ``POST /uploads/presign`` with ``{filename, content_type, size}``
       → receives ``{upload_url, key, mode, ...}``.
    2. Client uploads directly (PUT) to ``upload_url`` when ``mode == "s3"``.
       For local storage fallback, the client falls back to the regular
       ``/process`` multipart upload path.
    3. Client ``POST /uploads/commit`` with ``{key, filename}`` to kick off the
       processing pipeline for the uploaded object.

This avoids funnelling multi-GB videos through the FastAPI process when an
S3-compatible backend is configured.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...storage import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)


class PresignRequest(BaseModel):
    filename: str
    content_type: Optional[str] = None
    size: Optional[int] = None


class CommitRequest(BaseModel):
    key: str
    filename: Optional[str] = None
    use_vision: bool = False


@router.post("/presign")
async def presign_upload(req: PresignRequest) -> dict:
    """Return a presigned PUT URL (or fallback descriptor) for a direct upload."""
    safe_name = req.filename.replace("/", "_").replace("\\", "_")
    key = f"uploads/{uuid.uuid4().hex}_{safe_name}"
    storage = get_storage()
    try:
        info = await storage.presign_put(key, expires_in=3600, content_type=req.content_type)
    except NotImplementedError:
        info = {
            "mode": "fallback",
            "method": "POST",
            "upload_url": "/api/v1/process",
            "key": key,
            "reason": "presign unsupported — use /process",
        }
    info["key"] = key
    info["original_filename"] = req.filename
    return info


@router.post("/commit")
async def commit_upload(req: CommitRequest) -> dict:
    """Mark a previously presigned upload as ready and enqueue processing.

    We defer to the durable queue so the object is processed exactly like
    a regular upload. If the backend can't stream the object back to the
    pipeline yet, the response includes a "pending" status so the client
    knows to retry once server-side streaming lands.
    """
    storage = get_storage()
    if not await storage.exists(req.key):
        raise HTTPException(status_code=404, detail=f"object not found: {req.key}")

    # Best-effort: materialise to a temp path so the existing pipeline
    # (which expects filesystem input) can pick it up.
    import tempfile
    from pathlib import Path

    data = await storage.get(req.key)
    suffix = Path(req.filename or req.key).suffix or ".mp4"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(data)
    tmp.flush()
    tmp.close()

    job_id = str(uuid.uuid4())
    frames_dir = tempfile.mkdtemp(prefix=f"frames_{job_id}_")
    try:
        from ...batch import durable_queue

        await durable_queue.enqueue_job(
            job_id=job_id,
            video_path=tmp.name,
            frames_dir=frames_dir,
            meta={"use_vision": req.use_vision, "source": "presigned"},
        )
        queued = True
    except Exception as exc:  # pragma: no cover — fallback to legacy path
        logger.warning("Durable queue unavailable, falling back to in-memory: %s", exc)
        from .process import _jobs
        _jobs[job_id] = {"status": "pending", "video_path": tmp.name, "result": None}
        queued = False

    return {
        "job_id": job_id,
        "key": req.key,
        "queued": queued,
        "local_path": tmp.name,
    }
