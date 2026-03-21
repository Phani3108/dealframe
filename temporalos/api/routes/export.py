"""Export API routes — download reports in various formats."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, HTMLResponse

router = APIRouter(prefix="/export", tags=["export"])


def _get_jobs() -> dict:
    from ...api.routes.process import _jobs
    return _jobs


@router.get("/{job_id}", response_model=None)
async def export_job(
    job_id: str,
    format: str = Query("json", description="Export format: json, csv, markdown, html"),
):
    """Export a job's intelligence in the specified format."""
    from ...export import export

    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    intel = job.get("intelligence")
    if not intel:
        raise HTTPException(400, "No intelligence data for this job")

    try:
        content = export(job_id, intel, format)
    except ValueError as e:
        raise HTTPException(400, str(e))

    content_types = {
        "json": "application/json",
        "csv": "text/csv",
        "markdown": "text/markdown",
        "md": "text/markdown",
        "html": "text/html",
    }

    if format.lower() == "html":
        return HTMLResponse(content=content)

    return PlainTextResponse(
        content=content,
        media_type=content_types.get(format.lower(), "text/plain"),
        headers={"Content-Disposition": f'attachment; filename="{job_id}.{format}"'},
    )
