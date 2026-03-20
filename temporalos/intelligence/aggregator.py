"""
Multi-video intelligence aggregator — Phase 3.

Aggregates extraction results across multiple processed videos to produce
portfolio-level intelligence: top objections, topic frequency trends,
risk score timelines, and competitor mention counts.

Architecture:
  - VideoAggregator: async class backed by a SQLAlchemy session (production)
  - _aggregate_*: pure-Python helpers that operate on duck-typed objects
    (used by VideoAggregator and directly in unit tests without a real DB)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class ObjectionSummary:
    text: str
    count: int
    example_timestamps: list[str] = field(default_factory=list)
    risk_avg: float = 0.0


@dataclass
class TopicTrend:
    topic: str
    counts_by_day: dict[str, int] = field(default_factory=dict)


@dataclass
class PortfolioRiskSummary:
    portfolio_id: str
    video_count: int
    avg_risk_score: float
    high_risk_video_count: int
    top_risk_topics: list[str] = field(default_factory=list)


# ── Pure-Python helpers (unit-testable without a DB session) ──────────────────

def _aggregate_objections(extractions: list, limit: int = 10) -> list[ObjectionSummary]:
    """
    Aggregate objections from a list of Extraction-like objects.
    Each object must have: .objections (list[str]), .risk_score (float),
    and optionally .segment (object with .timestamp_str).
    """
    counter: dict[str, list[dict]] = defaultdict(list)

    for ext in extractions:
        for obj in (getattr(ext, "objections", None) or []):
            obj_str = str(obj).strip()
            if not obj_str:
                continue
            seg = getattr(ext, "segment", None)
            ts = getattr(seg, "timestamp_str", "") if seg else ""
            counter[obj_str.lower()].append({
                "display": obj_str,
                "timestamp": ts,
                "risk_score": float(getattr(ext, "risk_score", 0.0)),
            })

    summaries: list[ObjectionSummary] = []
    for key, items in sorted(counter.items(), key=lambda x: -len(x[1]))[:limit]:
        summaries.append(
            ObjectionSummary(
                text=items[0]["display"],
                count=len(items),
                example_timestamps=[i["timestamp"] for i in items[:3] if i["timestamp"]],
                risk_avg=round(sum(i["risk_score"] for i in items) / len(items), 2),
            )
        )
    return summaries


def _aggregate_topic_trends(extractions: list) -> list[TopicTrend]:
    """Group extractions by topic and day (requires .topic and .created_at)."""
    trends: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for ext in extractions:
        created_at = getattr(ext, "created_at", None)
        if not created_at:
            continue
        day = created_at.strftime("%Y-%m-%d")
        topic = getattr(ext, "topic", "other")
        trends[topic][day] += 1

    return [TopicTrend(topic=t, counts_by_day=dict(d)) for t, d in trends.items()]


# ── DB-backed aggregator ───────────────────────────────────────────────────────

class VideoAggregator:
    """
    Phase 3 — Multi-video Intelligence.

    Queries the extractions + videos tables to build cross-video analytics.
    Pass a SQLAlchemy AsyncSession from get_session().
    """

    def __init__(self, session: object) -> None:
        self._session = session

    async def top_objections(
        self,
        portfolio_id: int | None = None,
        limit: int = 10,
    ) -> list[ObjectionSummary]:
        from sqlalchemy import select

        from ..db.models import Extraction, Segment, Video

        stmt = select(Extraction)
        if portfolio_id is not None:
            from ..db.models import PortfolioVideo

            stmt = (
                stmt
                .join(Segment, Extraction.segment_id == Segment.id)
                .join(Video, Segment.video_id == Video.id)
                .join(PortfolioVideo, PortfolioVideo.video_id == Video.id)
                .where(PortfolioVideo.portfolio_id == portfolio_id)
            )

        result = await self._session.execute(stmt)  # type: ignore[union-attr]
        extractions = result.scalars().all()
        return _aggregate_objections(extractions, limit=limit)

    async def topic_trends(self, days: int = 30) -> list[TopicTrend]:
        from sqlalchemy import select

        from ..db.models import Extraction

        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(Extraction).where(Extraction.created_at >= cutoff)
        result = await self._session.execute(stmt)  # type: ignore[union-attr]
        return _aggregate_topic_trends(result.scalars().all())

    async def risk_summary(
        self,
        portfolio_id: int | None = None,
    ) -> PortfolioRiskSummary:
        from sqlalchemy import select

        from ..db.models import Extraction, Video

        stmt = select(Video)
        if portfolio_id is not None:
            from ..db.models import PortfolioVideo

            stmt = stmt.join(
                PortfolioVideo, PortfolioVideo.video_id == Video.id
            ).where(PortfolioVideo.portfolio_id == portfolio_id)

        video_result = await self._session.execute(stmt)  # type: ignore[union-attr]
        videos = video_result.scalars().all()

        risk_scores = [v.overall_risk_score for v in videos if v.overall_risk_score is not None]
        high_risk = [v for v in videos if (v.overall_risk_score or 0.0) >= 0.7]

        # Top risk topics from high-risk extractions
        ext_stmt = select(Extraction).where(Extraction.risk == "high")
        ext_result = await self._session.execute(ext_stmt)  # type: ignore[union-attr]
        high_risk_exts = ext_result.scalars().all()

        topic_counts: dict[str, int] = {}
        for ext in high_risk_exts:
            topic_counts[ext.topic] = topic_counts.get(ext.topic, 0) + 1
        top_topics = sorted(topic_counts, key=lambda x: -topic_counts[x])[:5]

        return PortfolioRiskSummary(
            portfolio_id=str(portfolio_id or "all"),
            video_count=len(videos),
            avg_risk_score=round(sum(risk_scores) / len(risk_scores), 3) if risk_scores else 0.0,
            high_risk_video_count=len(high_risk),
            top_risk_topics=top_topics,
        )
