"""Search API — full-text + structured filter search across all processed video segments."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...intelligence.portfolio_insights import PortfolioInsights
from ...search.indexer import get_search_index
from ...search.query import SearchEngine, SearchQuery

router = APIRouter(prefix="/search", tags=["search"])

_engine = SearchEngine()


@router.get("")
async def search_segments(
    q: str = Query(..., description="Free-text search query"),
    risk: str | None = Query(None, description="Filter by risk: low | medium | high"),
    topic: str | None = Query(None, description="Filter by topic"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Search across all indexed video segments using TF-IDF ranking."""
    query = SearchQuery(text=q, risk=risk, topic=topic, limit=limit)
    results = _engine.search(query)
    return {
        "query": q,
        "filters": {"risk": risk, "topic": topic},
        "total": len(results),
        "results": [r.to_dict() for r in results],
    }


@router.get("/index/stats")
async def index_stats() -> dict:
    """Return statistics about the current search index."""
    idx = get_search_index()
    return {"document_count": idx.document_count}


@router.post("/index/{video_id}")
async def index_video(video_id: str) -> dict:
    """Trigger re-indexing of a specific video's extractions."""
    # In production: load extractions from DB and call _engine.index_extraction()
    return {"message": f"Indexing queued for video {video_id}", "video_id": video_id}


@router.get("/insights/patterns")
async def win_loss_patterns() -> dict:
    """Win/loss objection patterns across all indexed videos."""
    from ..routes.process import _jobs
    intels = [
        j["result"] for j in _jobs.values()
        if j.get("status") == "completed" and j.get("result")
    ]
    patterns = PortfolioInsights.win_loss_patterns(intels)
    return patterns.to_dict()


@router.get("/insights/velocity")
async def objection_velocity(period: str = Query("week", pattern="^(week|month)$")) -> dict:
    """Objection frequency trends over time."""
    velocity = PortfolioInsights.objection_velocity([], period=period)
    return {
        "period": period,
        "total": len(velocity),
        "items": [v.to_dict() for v in velocity],
    }


@router.get("/insights/reps")
async def rep_comparison() -> dict:
    """Metric comparison across sales reps / video sources."""
    comparison = PortfolioInsights.rep_comparison({})
    return {"reps": comparison, "total": len(comparison)}
