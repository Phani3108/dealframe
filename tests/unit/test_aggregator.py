"""Unit tests — multi-video intelligence aggregator (pure-Python layer)."""

from datetime import datetime

import pytest

from temporalos.intelligence.aggregator import (
    ObjectionSummary,
    TopicTrend,
    _aggregate_objections,
    _aggregate_topic_trends,
)


class _FakeExtraction:
    """Minimal duck-type for Extraction ORM, used in tests without a real DB."""

    def __init__(
        self,
        objections: list[str],
        topic: str = "pricing",
        risk: str = "medium",
        risk_score: float = 0.5,
        created_at: datetime | None = None,
    ) -> None:
        self.objections = objections
        self.topic = topic
        self.risk = risk
        self.risk_score = risk_score
        self.created_at = created_at or datetime.utcnow()
        self.segment = None


class TestAggregateObjections:
    def test_empty_returns_empty(self):
        assert _aggregate_objections([]) == []

    def test_empty_objection_lists_returns_empty(self):
        exts = [_FakeExtraction(objections=[]) for _ in range(5)]
        assert _aggregate_objections(exts) == []

    def test_counts_single_objection(self):
        exts = [_FakeExtraction(["price too high"]) for _ in range(3)]
        result = _aggregate_objections(exts)
        assert len(result) == 1
        assert result[0].count == 3
        assert result[0].text.lower() == "price too high"

    def test_ordering_by_frequency(self):
        exts = [
            _FakeExtraction(["price too high"]),
            _FakeExtraction(["price too high"]),
            _FakeExtraction(["needs integration", "price too high"]),
            _FakeExtraction(["needs integration"]),
        ]
        result = _aggregate_objections(exts)
        assert result[0].count >= result[1].count  # sorted descending

    def test_case_insensitive_deduplication(self):
        exts = [
            _FakeExtraction(["Price is High"]),
            _FakeExtraction(["price is high"]),
            _FakeExtraction(["PRICE IS HIGH"]),
        ]
        result = _aggregate_objections(exts)
        assert len(result) == 1
        assert result[0].count == 3

    def test_limit_respected(self):
        exts = [_FakeExtraction([f"objection {i}"]) for i in range(20)]
        result = _aggregate_objections(exts, limit=5)
        assert len(result) == 5

    def test_risk_avg_computed(self):
        exts = [
            _FakeExtraction(["too expensive"], risk_score=0.8),
            _FakeExtraction(["too expensive"], risk_score=0.4),
        ]
        result = _aggregate_objections(exts)
        assert result[0].risk_avg == pytest.approx(0.6)

    def test_blank_strings_ignored(self):
        exts = [_FakeExtraction(["", "  ", "valid objection"])]
        result = _aggregate_objections(exts)
        assert len(result) == 1
        assert result[0].text == "valid objection"


class TestAggregateTopicTrends:
    def test_empty_returns_empty(self):
        assert _aggregate_topic_trends([]) == []

    def test_groups_by_topic(self):
        exts = [
            _FakeExtraction([], topic="pricing", created_at=datetime(2026, 3, 1)),
            _FakeExtraction([], topic="features", created_at=datetime(2026, 3, 1)),
        ]
        trends = _aggregate_topic_trends(exts)
        topics = [t.topic for t in trends]
        assert "pricing" in topics
        assert "features" in topics

    def test_counts_by_day(self):
        exts = [
            _FakeExtraction([], topic="pricing", created_at=datetime(2026, 3, 1)),
            _FakeExtraction([], topic="pricing", created_at=datetime(2026, 3, 1)),
            _FakeExtraction([], topic="pricing", created_at=datetime(2026, 3, 2)),
        ]
        trends = _aggregate_topic_trends(exts)
        pricing = next(t for t in trends if t.topic == "pricing")
        assert pricing.counts_by_day["2026-03-01"] == 2
        assert pricing.counts_by_day["2026-03-02"] == 1

    def test_missing_created_at_skipped(self):
        exts = [_FakeExtraction([], topic="pricing", created_at=None)]
        exts[0].created_at = None  # type: ignore[assignment]
        result = _aggregate_topic_trends(exts)
        pricing = next((t for t in result if t.topic == "pricing"), None)
        assert pricing is None or pricing.counts_by_day == {}
