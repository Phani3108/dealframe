"""Process route — submit a video for analysis, poll for results.

Jobs are persisted to the database and survive server restarts.
An in-memory cache provides fast reads; the DB is the source of truth.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from ...alignment.aligner import align
from ...audio.whisper import transcribe
from ...config import get_settings
from ...extraction.models.gpt4o import GPT4oExtractionModel
from ...ingestion.extractor import extract_frames, get_video_duration_ms
from ...ingestion.url_downloader import download_video, is_supported_url
from ...observability.telemetry import get_tracer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["process"])

# In-memory cache backed by DB.  Populated on startup, updated on writes.
_jobs: dict[str, dict] = {}


async def _db_save_job(job_id: str, data: dict) -> None:
    """Persist job state to the database (fire-and-forget safe)."""
    try:
        from ...db.session import get_session_factory
        sf = get_session_factory()
        if not sf:
            return
        from ...db.models import JobRecord
        from sqlalchemy import select
        async with sf() as sess:
            row = (await sess.execute(
                select(JobRecord).where(JobRecord.id == job_id)
            )).scalar_one_or_none()
            if row is None:
                row = JobRecord(id=job_id)
                sess.add(row)
            row.status = data.get("status", "pending")
            row.video_path = data.get("video_path", "")
            row.frames_dir = data.get("frames_dir", "")
            row.stages_done = data.get("stages_done", [])
            row.result = data.get("result")
            row.error = data.get("error")
            await sess.commit()
    except Exception as exc:
        logger.warning("Failed to persist job %s: %s", job_id, exc)


async def load_jobs_from_db() -> None:
    """Load all jobs from the database into the in-memory cache."""
    try:
        from ...db.session import get_session_factory
        sf = get_session_factory()
        if not sf:
            return
        from ...db.models import JobRecord
        from sqlalchemy import select
        async with sf() as sess:
            rows = (await sess.execute(select(JobRecord))).scalars().all()
            for row in rows:
                _jobs[row.id] = {
                    "status": row.status,
                    "video_path": row.video_path or "",
                    "frames_dir": row.frames_dir or "",
                    "stages_done": row.stages_done or [],
                    "result": row.result,
                    "error": row.error,
                }
        logger.info("Loaded %d jobs from database", len(rows))
    except Exception as exc:
        logger.warning("Failed to load jobs from DB: %s", exc)


async def _db_save_search_docs(job_id: str, results: list[dict]) -> None:
    """Persist search index entries to the database."""
    try:
        from ...db.session import get_session_factory
        sf = get_session_factory()
        if not sf:
            return
        from ...db.models import SearchDocRecord
        async with sf() as sess:
            for r in results:
                doc_id = f"{job_id}:{r.get('timestamp', '')}"
                rec = SearchDocRecord(
                    id=doc_id,
                    video_id=job_id,
                    timestamp_ms=0,
                    topic=r.get("topic", ""),
                    risk=r.get("risk", ""),
                    risk_score=r.get("risk_score", 0),
                    objections=r.get("objections", []),
                    decision_signals=r.get("decision_signals", []),
                    transcript="",
                    model=r.get("model", ""),
                )
                await sess.merge(rec)
            await sess.commit()
    except Exception as exc:
        logger.warning("Failed to persist search docs: %s", exc)


def _run_pipeline(job_id: str, video_path: str, frames_dir: str) -> None:
    """Synchronous pipeline runner (runs in thread-pool)."""
    tracer = get_tracer()
    settings = get_settings()

    with tracer.start_as_current_span("pipeline.run") as span:
        span.set_attribute("pipeline.job_id", job_id)

        try:
            _jobs[job_id]["status"] = "processing"
            asyncio.get_event_loop().run_until_complete(
                _db_save_job(job_id, _jobs[job_id]))

            # ── Stage 1: Frame extraction
            frames = extract_frames(
                video_path=video_path,
                output_dir=frames_dir,
                interval_seconds=settings.video.frame_interval_seconds,
                max_resolution=settings.video.max_resolution,
            )
            _jobs[job_id]["stages_done"].append("frame_extraction")
            span.set_attribute("pipeline.frame_count", len(frames))

            # ── Stage 2: Transcription
            language = (
                settings.audio.language
                if settings.audio.language != "auto"
                else None
            )
            words = transcribe(
                video_path=video_path,
                model_name=settings.audio.whisper_model,
                language=language,
            )
            _jobs[job_id]["stages_done"].append("transcription")
            span.set_attribute("pipeline.word_count", len(words))

            # ── Stage 3: Temporal alignment
            segments = align(frames, words)
            _jobs[job_id]["stages_done"].append("alignment")

            # ── Stage 4: Structured extraction
            extractor = GPT4oExtractionModel.from_settings()
            min_words = settings.extraction.min_words_per_segment
            results: list[dict] = []

            for seg in segments:
                if len(seg.words) < min_words:
                    continue
                ext = extractor.extract(seg)
                results.append({"timestamp": seg.timestamp_str, **ext.to_dict()})

            _jobs[job_id]["stages_done"].append("extraction")

            overall_risk = (
                round(sum(r["risk_score"] for r in results) / len(results), 2)
                if results
                else 0.0
            )

            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = {
                "segments": results,
                "overall_risk_score": overall_risk,
                "segment_count": len(results),
            }
            span.set_attribute("pipeline.segments_extracted", len(results))

            # Persist completed result + index for search
            asyncio.get_event_loop().run_until_complete(
                _db_save_job(job_id, _jobs[job_id]))

            # Auto-index into search
            try:
                from ...search.indexer import IndexEntry, get_search_index
                idx = get_search_index()
                for r in results:
                    entry = IndexEntry(
                        doc_id=f"{job_id}:{r.get('timestamp', '')}",
                        video_id=job_id,
                        timestamp_ms=0,
                        timestamp_str=r.get("timestamp", ""),
                        topic=r.get("topic", ""),
                        risk=r.get("risk", ""),
                        risk_score=r.get("risk_score", 0),
                        objections=r.get("objections", []),
                        decision_signals=r.get("decision_signals", []),
                        transcript="",
                        model=r.get("model", ""),
                    )
                    idx.index(entry)
                # Persist search docs to DB
                asyncio.get_event_loop().run_until_complete(
                    _db_save_search_docs(job_id, results))
            except Exception:
                pass

        except Exception as exc:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)
            span.record_exception(exc)
            span.set_attribute("pipeline.error", str(exc))
            asyncio.get_event_loop().run_until_complete(
                _db_save_job(job_id, _jobs[job_id]))


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/process", status_code=202)
async def process_video(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    video_url: Optional[str] = Form(None),
) -> dict:
    """Submit a video for processing.

    Accepts either:
    - ``file``: a multipart video file upload, OR
    - ``video_url``: a URL to a YouTube video or any yt-dlp supported source.

    Exactly one of the two must be provided.
    """
    settings = get_settings()
    job_id = str(uuid.uuid4())
    upload_dir = Path(settings.app.upload_dir)
    frames_dir = str(Path(settings.app.frames_dir) / job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    if video_url:
        # ── URL ingestion path (YouTube, Vimeo, Loom, etc.)
        if not is_supported_url(video_url):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported URL scheme. Must start with http:// or https://",
            )
        try:
            video_path = download_video(video_url, upload_dir)
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except ImportError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    elif file is not None:
        # ── File upload path
        suffix = Path(file.filename or "").suffix.lower().lstrip(".")
        if suffix not in settings.video.supported_formats:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported format '{suffix}'. "
                    f"Supported: {settings.video.supported_formats}"
                ),
            )
        video_path = str(upload_dir / f"{job_id}.{suffix}")
        with open(video_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Persist to configured storage backend (local/S3)
        try:
            from ...storage import get_storage
            storage = get_storage()
            with open(video_path, "rb") as vf:
                video_bytes = vf.read()
            asyncio.ensure_future(
                storage.put(f"uploads/{job_id}.mp4", video_bytes))
        except Exception:
            pass  # Storage backend optional — local copy always exists

    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'file' (upload) or 'video_url' (YouTube/URL).",
        )

    _jobs[job_id] = {
        "status": "pending",
        "stages_done": [],
        "video_path": video_path,
        "frames_dir": frames_dir,
        "source_url": video_url or "",
    }
    await _db_save_job(job_id, _jobs[job_id])
    background_tasks.add_task(_run_pipeline, job_id, video_path, frames_dir)

    return {"job_id": job_id, "status": "pending", "source_url": video_url or ""}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """Poll pipeline progress and retrieve results when completed."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job_id": job_id, **job}


@router.get("/jobs")
async def list_jobs() -> dict:
    """List all jobs and their statuses."""
    summary = {
        jid: {"status": j["status"], "stages_done": j.get("stages_done", [])}
        for jid, j in _jobs.items()
    }
    return {"jobs": summary, "total": len(_jobs)}
