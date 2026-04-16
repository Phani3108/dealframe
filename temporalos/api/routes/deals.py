"""Deal Inbox — a compact listing of every video as a "deal row" with the
stats the sales floor wants to see: risk heat, top topic, top objection,
segment count, stage.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deals", tags=["deals"])


def _summarize_job(job_id: str, job: dict) -> dict:
    intel = job.get("result") or job.get("intelligence") or {}
    segments = intel.get("segments") or []

    topics: list[str] = []
    objections: list[str] = []
    high_risk = 0
    for s in segments:
        ext = s.get("extraction") if isinstance(s, dict) and "extraction" in s else s
        topics.append((ext.get("topic") or "other"))
        objections.extend(ext.get("objections") or [])
        if ext.get("risk") == "high":
            high_risk += 1

    overall = float(intel.get("overall_risk_score") or 0.0)
    top_topic = Counter(topics).most_common(1)[0][0] if topics else None
    top_obj = Counter(objections).most_common(1)[0][0] if objections else None

    status = job.get("status", "pending")
    stage = (
        "analysed" if status == "completed"
        else "failed" if status == "failed"
        else "processing"
    )

    return {
        "job_id": job_id,
        "title": (job.get("source_url") or f"Deal {job_id[:8]}")[:80],
        "status": status,
        "stage": stage,
        "created_at": job.get("created_at"),
        "duration_ms": intel.get("duration_ms"),
        "overall_risk_score": round(overall, 3),
        "segment_count": len(segments),
        "high_risk_count": high_risk,
        "top_topic": top_topic,
        "top_objection": top_obj,
    }


@router.get("")
async def list_deals(limit: int = Query(200, ge=1, le=1000)) -> dict:
    from .process import _jobs
    rows = [_summarize_job(jid, j) for jid, j in _jobs.items()]
    # Sort: processing first, then by risk score desc, then by segment count.
    rows.sort(key=lambda r: (
        0 if r["status"] == "processing" else 1,
        -r["overall_risk_score"],
        -r["segment_count"],
    ))
    return {"deals": rows[:limit]}


@router.get("/summary")
async def deals_summary() -> dict:
    from .process import _jobs
    total = len(_jobs)
    completed = sum(1 for j in _jobs.values() if j.get("status") == "completed")
    processing = sum(1 for j in _jobs.values() if j.get("status") in {"pending", "processing"})
    failed = sum(1 for j in _jobs.values() if j.get("status") == "failed")
    risks: list[float] = []
    total_segments = 0
    high_risk_deals = 0
    for j in _jobs.values():
        intel = j.get("result") or j.get("intelligence") or {}
        overall = float(intel.get("overall_risk_score") or 0.0)
        risks.append(overall)
        total_segments += len(intel.get("segments") or [])
        if overall > 0.6:
            high_risk_deals += 1
    avg_risk = round(sum(risks) / len(risks), 3) if risks else 0.0
    return {
        "total": total,
        "completed": completed,
        "processing": processing,
        "failed": failed,
        "avg_risk": avg_risk,
        "total_segments": total_segments,
        "high_risk_deals": high_risk_deals,
    }
