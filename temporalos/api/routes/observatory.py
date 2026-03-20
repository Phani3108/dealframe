"""Observatory route — compare multiple extraction models on the same video."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from ...alignment.aligner import align
from ...audio.whisper import transcribe
from ...config import get_settings
from ...extraction.models.claude import ClaudeExtractionModel
from ...extraction.models.gpt4o import GPT4oExtractionModel
from ...ingestion.extractor import extract_frames
from ...observatory.runner import ObservatoryRunner
from ...observability.telemetry import get_tracer

router = APIRouter(tags=["observatory"])

# In-memory session store (Phase 3 will migrate to DB)
_sessions: dict[str, dict] = {}


# ── Background runner ──────────────────────────────────────────────────────────

def _run_observatory(session_id: str, video_path: str, frames_dir: str) -> None:
    """
    Full pipeline: extract → transcribe → align → run all models → compare.
    Runs in FastAPI's thread-pool executor.
    """
    settings = get_settings()
    tracer = get_tracer()

    with tracer.start_as_current_span("observatory.session") as span:
        span.set_attribute("observatory.session_id", session_id)

        try:
            _sessions[session_id]["status"] = "processing"

            # ── Pipeline ──────────────────────────────────────────────────────
            frames = extract_frames(
                video_path=video_path,
                output_dir=frames_dir,
                interval_seconds=settings.video.frame_interval_seconds,
                max_resolution=settings.video.max_resolution,
            )
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
            segments = align(frames, words)

            # ── Multi-model comparison ─────────────────────────────────────────
            runner = ObservatoryRunner(max_workers=4)
            runner.register_extractor(GPT4oExtractionModel.from_settings())
            runner.register_extractor(ClaudeExtractionModel.from_settings())

            runs = runner.run(segments)
            report = runner.compare(runs, session_id=session_id)

            _sessions[session_id]["status"] = "completed"
            _sessions[session_id]["report"] = report.to_dict()
            _sessions[session_id]["total_runs"] = len(runs)

            span.set_attribute("observatory.runs_completed", len(runs))

        except Exception as exc:
            _sessions[session_id]["status"] = "failed"
            _sessions[session_id]["error"] = str(exc)
            span.record_exception(exc)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/observatory/compare", status_code=202)
async def compare_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict:
    """
    Submit a video for multi-model Observatory comparison.
    Runs GPT-4o and Claude on every segment in parallel.
    Returns a session_id to poll.
    """
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")

    if suffix not in settings.video.supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{suffix}'. Supported: {settings.video.supported_formats}",
        )

    session_id = str(uuid.uuid4())
    upload_dir = Path(settings.app.upload_dir)
    frames_dir = str(Path(settings.app.frames_dir) / f"obs_{session_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = str(upload_dir / f"obs_{session_id}.{suffix}")

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    _sessions[session_id] = {"status": "pending"}
    background_tasks.add_task(_run_observatory, session_id, video_path, frames_dir)

    return {"session_id": session_id, "status": "pending"}


@router.get("/observatory/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """Retrieve Observatory session status and comparison report."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"session_id": session_id, **session}


@router.get("/observatory/sessions")
async def list_sessions() -> dict:
    """List all Observatory sessions."""
    return {
        "sessions": [
            {"session_id": sid, "status": s["status"]}
            for sid, s in _sessions.items()
        ],
        "total": len(_sessions),
    }
