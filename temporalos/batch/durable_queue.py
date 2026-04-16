"""DB-backed durable job queue.

Replaces the process-local heap in ``queue.py`` for the main video pipeline.
Jobs live in the ``jobs`` table (``JobRecord``); an asyncio poll loop claims
``pending`` rows, runs the pipeline, and publishes progress events to the
in-process ``EventBus`` (so SSE consumers see live updates).

This queue is **single-process** on purpose — it survives restarts (durability)
but does not require Redis or a separate worker service. Scale out by adding
more replicas and a row-lock claim.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from ..observability.event_bus import get_event_bus

logger = logging.getLogger(__name__)


async def _sf():
    from ..db.session import get_session_factory
    return get_session_factory()


async def enqueue_job(job_id: str, video_path: str, frames_dir: str, meta: Optional[dict] = None) -> None:
    """Mark a job row as pending and emit an 'enqueued' event."""
    sf = await _sf()
    if sf is None:
        return
    from ..db.models import JobRecord
    from sqlalchemy import select
    async with sf() as sess:
        row = (await sess.execute(
            select(JobRecord).where(JobRecord.id == job_id)
        )).scalar_one_or_none()
        if row is None:
            row = JobRecord(id=job_id)
            sess.add(row)
        row.status = "pending"
        row.video_path = video_path
        row.frames_dir = frames_dir
        row.stages_done = []
        row.error = None
        await sess.commit()
    await publish_event(job_id, "enqueued", "info", {"video_path": video_path, **(meta or {})})


async def publish_event(
    job_id: str, stage: str, status: str = "info", detail: Optional[dict] = None,
) -> None:
    """Append an event row + publish on the in-process bus."""
    detail = detail or {}
    sf = await _sf()
    if sf is not None:
        try:
            from ..db.models import JobEvent
            async with sf() as sess:
                sess.add(JobEvent(
                    job_id=job_id, stage=stage, status=status, detail=detail,
                ))
                await sess.commit()
        except Exception as exc:  # pragma: no cover — non-fatal
            logger.debug("event persist skipped: %s", exc)

    get_event_bus().publish(f"job:{job_id}", {
        "job_id": job_id, "stage": stage, "status": status,
        "detail": detail, "created_at": datetime.utcnow().isoformat(),
    })


async def _claim_next_pending() -> Optional[dict]:
    """Claim the oldest pending job by flipping its status to 'processing'."""
    sf = await _sf()
    if sf is None:
        return None
    from ..db.models import JobRecord
    from sqlalchemy import select
    async with sf() as sess:
        row = (await sess.execute(
            select(JobRecord)
            .where(JobRecord.status == "pending")
            .order_by(JobRecord.created_at.asc())
            .limit(1)
        )).scalar_one_or_none()
        if row is None:
            return None
        row.status = "processing"
        await sess.commit()
        return {
            "id": row.id, "video_path": row.video_path, "frames_dir": row.frames_dir,
        }


async def _mark_done(job_id: str, result: dict) -> None:
    sf = await _sf()
    if sf is None:
        return
    from ..db.models import JobRecord
    from sqlalchemy import select
    async with sf() as sess:
        row = (await sess.execute(
            select(JobRecord).where(JobRecord.id == job_id)
        )).scalar_one_or_none()
        if row is None:
            return
        row.status = "completed"
        row.result = result
        await sess.commit()


async def _mark_failed(job_id: str, error: str) -> None:
    sf = await _sf()
    if sf is None:
        return
    from ..db.models import JobRecord
    from sqlalchemy import select
    async with sf() as sess:
        row = (await sess.execute(
            select(JobRecord).where(JobRecord.id == job_id)
        )).scalar_one_or_none()
        if row is None:
            return
        row.status = "failed"
        row.error = error
        await sess.commit()


# ── Worker loop ────────────────────────────────────────────────────────────────

_stop = asyncio.Event()
_worker_task: Optional[asyncio.Task] = None


async def _run_pipeline_with_events(job_id: str, video_path: str, frames_dir: str) -> None:
    """Run the full pipeline, publishing a progress event per stage."""
    # Import lazily so the module can be loaded without heavy ML deps present.
    from ..alignment.aligner import align
    from ..audio.whisper import transcribe
    from ..config import get_settings
    from ..extraction.models.gpt4o import GPT4oExtractionModel
    from ..ingestion.extractor import extract_frames
    from .. import observability as obs  # noqa: F401 (side-effects)
    from ..api.routes import process as process_route  # update in-memory cache too

    settings = get_settings()
    process_route._jobs.setdefault(job_id, {})
    cache = process_route._jobs[job_id]
    cache.setdefault("stages_done", [])
    cache["status"] = "processing"
    cache["video_path"] = video_path
    cache["frames_dir"] = frames_dir

    try:
        await publish_event(job_id, "ingest", "progress", {"pct": 5})
        frames = await asyncio.to_thread(
            extract_frames,
            video_path=video_path,
            output_dir=frames_dir,
            interval_seconds=settings.video.frame_interval_seconds,
            max_resolution=settings.video.max_resolution,
        )
        cache["stages_done"].append("frame_extraction")
        await publish_event(job_id, "ingest", "done", {"frames": len(frames)})

        await publish_event(job_id, "transcribe", "progress", {"pct": 25})
        language = settings.audio.language if settings.audio.language != "auto" else None
        words = await asyncio.to_thread(
            transcribe,
            video_path=video_path,
            model_name=settings.audio.whisper_model,
            language=language,
        )
        cache["stages_done"].append("transcription")
        await publish_event(job_id, "transcribe", "done", {"words": len(words)})

        await publish_event(job_id, "diarize", "progress", {"pct": 45})
        from ..diarization.diarizer import get_diarizer
        from ..diarization.speaker_intel import compute_speaker_intelligence
        diarizer = get_diarizer()
        words = await asyncio.to_thread(diarizer.diarize, words)
        speaker_intel = await asyncio.to_thread(compute_speaker_intelligence, words)
        cache["stages_done"].append("diarization")
        await publish_event(job_id, "diarize", "done", {})

        await publish_event(job_id, "align", "progress", {"pct": 60})
        segments = await asyncio.to_thread(align, frames, words)
        cache["stages_done"].append("alignment")
        await publish_event(job_id, "align", "done", {"segments": len(segments)})

        # ── OCR enrichment: feed on-screen text into the extraction prompt ────
        # The extractors (gpt4o / claude) read `segment.ocr_text` when present,
        # so slide/screen content becomes part of the default extraction prompt.
        try:
            await publish_event(job_id, "vision", "progress", {"pct": 65})
            from ..vision.pipeline import VisionPipeline
            vp = VisionPipeline(run_ocr=True, run_classification=True)
            enriched_frames = await asyncio.to_thread(vp.process, frames)
            ocr_by_ts = {ef.timestamp_ms: ef for ef in enriched_frames}
            for seg in segments:
                if seg.frame is not None and seg.frame.timestamp_ms in ocr_by_ts:
                    ef = ocr_by_ts[seg.frame.timestamp_ms]
                    seg.ocr_text = ef.ocr_text
                    seg.frame_type = getattr(ef.frame_type, "value", str(ef.frame_type))
            ocr_hits = sum(1 for s in segments if getattr(s, "ocr_text", ""))
            await publish_event(job_id, "vision", "done", {"ocr_hits": ocr_hits})
        except Exception as exc:  # OCR is best-effort — never block extraction.
            logger.debug("OCR enrichment skipped: %s", exc)
            await publish_event(job_id, "vision", "skipped", {"reason": str(exc)})

        await publish_event(job_id, "extract", "progress", {"pct": 70})
        extractor = GPT4oExtractionModel.from_settings()
        min_words = settings.extraction.min_words_per_segment
        results: list[dict] = []
        total = max(1, len(segments))
        for i, seg in enumerate(segments):
            if len(seg.words) < min_words:
                continue
            ext = await asyncio.to_thread(extractor.extract, seg)
            results.append({"timestamp": seg.timestamp_str, **ext.to_dict()})
            if i % 5 == 0:
                pct = 70 + int(25 * i / total)
                await publish_event(
                    job_id, "extract", "progress",
                    {"pct": pct, "segments_done": len(results), "segments_total": total},
                )

        cache["stages_done"].append("extraction")
        overall_risk = (
            round(sum(r["risk_score"] for r in results) / len(results), 2)
            if results else 0.0
        )
        intel = {
            "segments": results,
            "overall_risk_score": overall_risk,
            "segment_count": len(results),
            "speaker_intelligence": speaker_intel.to_dict(),
        }
        cache["status"] = "completed"
        cache["result"] = intel
        await _mark_done(job_id, intel)
        await publish_event(job_id, "done", "done", {
            "segments": len(results),
            "overall_risk_score": overall_risk,
        })

        # Auto-index into search (best-effort)
        try:
            from ..search.indexer import IndexEntry, get_search_index
            idx = get_search_index()
            for r in results:
                idx.index(IndexEntry(
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
                ))
        except Exception:
            pass

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        cache["status"] = "failed"
        cache["error"] = str(exc)
        await _mark_failed(job_id, str(exc))
        await publish_event(job_id, "failed", "error", {"message": str(exc)})


async def _worker_loop(poll_interval: float = 1.0) -> None:
    """Single-consumer poll loop. Runs inside the FastAPI event loop."""
    logger.info("Durable job worker started")
    while not _stop.is_set():
        try:
            job = await _claim_next_pending()
            if job is None:
                try:
                    await asyncio.wait_for(_stop.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass
                continue
            await _run_pipeline_with_events(job["id"], job["video_path"], job["frames_dir"])
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("worker loop error: %s", exc)
            await asyncio.sleep(poll_interval)
    logger.info("Durable job worker stopped")


def start_worker(loop: Optional[asyncio.AbstractEventLoop] = None) -> asyncio.Task:
    """Start the background worker task on the current event loop."""
    global _worker_task
    _stop.clear()
    if _worker_task is not None and not _worker_task.done():
        return _worker_task
    _worker_task = asyncio.create_task(_worker_loop())
    return _worker_task


async def stop_worker() -> None:
    global _worker_task
    _stop.set()
    if _worker_task is not None:
        try:
            await asyncio.wait_for(_worker_task, timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            _worker_task.cancel()
        _worker_task = None
