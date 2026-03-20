"""Intelligence route — multi-video portfolio analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...db.session import get_session
from ...intelligence.aggregator import VideoAggregator

router = APIRouter(tags=["intelligence"])


@router.get("/intelligence/objections")
async def top_objections(
    portfolio_id: int | None = Query(None, description="Filter to a specific portfolio"),
    limit: int = Query(10, ge=1, le=100),
    session=Depends(get_session),
) -> dict:
    """Return the most frequently raised objections across processed videos."""
    agg = VideoAggregator(session)
    results = await agg.top_objections(portfolio_id=portfolio_id, limit=limit)
    return {
        "objections": [
            {
                "text": r.text,
                "count": r.count,
                "example_timestamps": r.example_timestamps,
                "risk_avg": r.risk_avg,
            }
            for r in results
        ]
    }


@router.get("/intelligence/topics/trend")
async def topic_trends(
    days: int = Query(30, ge=1, le=365),
    session=Depends(get_session),
) -> dict:
    """Return topic frequency trends over the last N days."""
    agg = VideoAggregator(session)
    trends = await agg.topic_trends(days=days)
    return {
        "trends": [
            {"topic": t.topic, "counts_by_day": t.counts_by_day}
            for t in trends
        ]
    }


@router.get("/intelligence/risk/summary")
async def risk_summary(
    portfolio_id: int | None = Query(None),
    session=Depends(get_session),
) -> dict:
    """Return a portfolio-level risk summary."""
    agg = VideoAggregator(session)
    summary = await agg.risk_summary(portfolio_id=portfolio_id)
    return {
        "portfolio_id": summary.portfolio_id,
        "video_count": summary.video_count,
        "avg_risk_score": summary.avg_risk_score,
        "high_risk_video_count": summary.high_risk_video_count,
        "top_risk_topics": summary.top_risk_topics,
    }


@router.post("/intelligence/portfolios", status_code=201)
async def create_portfolio(
    name: str = Query(..., description="Portfolio display name"),
    description: str | None = Query(None),
    session=Depends(get_session),
) -> dict:
    """Create a named portfolio to group related videos."""
    from ...db.models import Portfolio
    from datetime import datetime

    portfolio = Portfolio(
        name=name,
        description=description,
        created_at=datetime.utcnow(),
    )
    session.add(portfolio)
    await session.commit()
    await session.refresh(portfolio)
    return {"portfolio_id": portfolio.id, "name": portfolio.name}


@router.post("/intelligence/portfolios/{portfolio_id}/videos", status_code=201)
async def add_video_to_portfolio(
    portfolio_id: int,
    video_id: int = Query(...),
    session=Depends(get_session),
) -> dict:
    """Add a processed video to a portfolio for aggregated analytics."""
    from ...db.models import Portfolio, PortfolioVideo, Video
    from datetime import datetime
    from sqlalchemy import select

    # Verify both exist
    portfolio = await session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail=f"Portfolio {portfolio_id} not found")

    video = await session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    pv = PortfolioVideo(
        portfolio_id=portfolio_id,
        video_id=video_id,
        added_at=datetime.utcnow(),
    )
    session.add(pv)
    await session.commit()
    return {"portfolio_id": portfolio_id, "video_id": video_id, "status": "added"}
