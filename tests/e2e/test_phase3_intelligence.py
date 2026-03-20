"""
Phase 3 end-to-end test — Multi-video Intelligence.

Tests the aggregation pipeline:
  Extraction objects → top objections / topic trends / risk summary → JSON API responses

Rules (from claude.md §0):
  - Pure-Python aggregation helpers tested without a real DB
  - API routes tested with dependency injection overrides (no real DB session)
  - VideoAggregator class patched in route tests so DB is never contacted
  - Must pass with 0 failures before Phase 3 is "done"
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from temporalos.intelligence.aggregator import (
    ObjectionSummary,
    PortfolioRiskSummary,
    TopicTrend,
    _aggregate_objections,
    _aggregate_topic_trends,
)


# ── Fake extraction objects (duck-type for Extraction ORM) ─────────────────────


class _FakeExt:
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
        self.created_at = created_at or datetime(2026, 3, 15)
        self.segment = None


# ── Pure-Python aggregation helpers ───────────────────────────────────────────


class TestObjectionAggregation:
    def test_empty_input_returns_empty(self):
        assert _aggregate_objections([]) == []

    def test_empty_objection_lists(self):
        assert _aggregate_objections([_FakeExt([]), _FakeExt([])]) == []

    def test_counts_single_objection_type(self):
        exts = [_FakeExt(["price is too high"]) for _ in range(4)]
        result = _aggregate_objections(exts)
        assert len(result) == 1
        assert result[0].count == 4
        assert result[0].text == "price is too high"

    def test_orders_by_frequency_descending(self):
        exts = [
            _FakeExt(["a", "a", "a"]),  # 3 × a
            _FakeExt(["b", "b"]),        # 2 × b
        ]
        # Flatten: 3 "a" and 2 "b" but written as separate entries
        exts2 = (
            [_FakeExt(["a"]) for _ in range(3)]
            + [_FakeExt(["b"]) for _ in range(2)]
        )
        result = _aggregate_objections(exts2)
        assert result[0].text == "a"
        assert result[0].count == 3
        assert result[1].count == 2

    def test_case_insensitive_grouping(self):
        exts = [_FakeExt(["Too Expensive"]), _FakeExt(["too expensive"]), _FakeExt(["TOO EXPENSIVE"])]
        result = _aggregate_objections(exts)
        assert len(result) == 1
        assert result[0].count == 3

    def test_limit_applied(self):
        exts = [_FakeExt([f"obj_{i}"]) for i in range(30)]
        assert len(_aggregate_objections(exts, limit=7)) == 7

    def test_risk_avg_computed_correctly(self):
        exts = [
            _FakeExt(["too costly"], risk_score=0.9),
            _FakeExt(["too costly"], risk_score=0.5),
        ]
        result = _aggregate_objections(exts)
        assert abs(result[0].risk_avg - 0.7) < 0.01

    def test_blank_and_whitespace_stripped(self):
        exts = [_FakeExt(["", "  ", "valid objection"])]
        result = _aggregate_objections(exts)
        assert len(result) == 1
        assert result[0].text == "valid objection"

    def test_multiple_objections_per_extraction(self):
        exts = [_FakeExt(["price", "timeline", "security"])]
        result = _aggregate_objections(exts)
        texts = {r.text for r in result}
        assert {"price", "timeline", "security"} == texts


class TestTopicTrendAggregation:
    def test_empty_returns_empty(self):
        assert _aggregate_topic_trends([]) == []

    def test_groups_by_topic(self):
        exts = [
            _FakeExt([], topic="pricing", created_at=datetime(2026, 3, 1)),
            _FakeExt([], topic="features", created_at=datetime(2026, 3, 1)),
        ]
        trends = _aggregate_topic_trends(exts)
        topics = {t.topic for t in trends}
        assert "pricing" in topics
        assert "features" in topics

    def test_daily_counts_summed(self):
        exts = [
            _FakeExt([], topic="pricing", created_at=datetime(2026, 3, 1)),
            _FakeExt([], topic="pricing", created_at=datetime(2026, 3, 1)),
            _FakeExt([], topic="pricing", created_at=datetime(2026, 3, 2)),
        ]
        trends = _aggregate_topic_trends(exts)
        pricing = next(t for t in trends if t.topic == "pricing")
        assert pricing.counts_by_day["2026-03-01"] == 2
        assert pricing.counts_by_day["2026-03-02"] == 1

    def test_none_created_at_skipped(self):
        e = _FakeExt([], topic="pricing")
        e.created_at = None  # type: ignore[assignment]
        result = _aggregate_topic_trends([e])
        pricing = next((t for t in result if t.topic == "pricing"), None)
        assert pricing is None or pricing.counts_by_day == {}


# ── Intelligence API tests ─────────────────────────────────────────────────────


class TestIntelligenceAPI:
    """
    Test /intelligence/* REST endpoints.

    Strategy:
      1. Override get_session dependency to avoid DB connection requirements.
      2. Patch VideoAggregator in the route module to return predetermined data.
      3. Assert correct HTTP status codes and response schema.
    """

    @pytest.fixture(autouse=True)
    def _client(self):
        with patch("temporalos.db.session.init_db", return_value=None):
            from temporalos.api.main import app
            from temporalos.db.session import get_session

            async def mock_session():
                yield MagicMock()

            app.dependency_overrides[get_session] = mock_session
            self._app = app
            self._tc = TestClient(app, raise_server_exceptions=True)
            yield
            app.dependency_overrides.pop(get_session, None)

    def _mock_aggregator(self, **method_return_values):
        mock_cls = MagicMock()
        instance = mock_cls.return_value
        for method, return_value in method_return_values.items():
            setattr(instance, method, AsyncMock(return_value=return_value))
        return mock_cls

    # ── /intelligence/objections ─────────────────────────────────────────────

    def test_objections_endpoint_returns_list(self):
        mock_cls = self._mock_aggregator(
            top_objections=[
                ObjectionSummary(text="price is high", count=5, example_timestamps=["00:12"], risk_avg=0.7),
                ObjectionSummary(text="needs integration", count=2, risk_avg=0.4),
            ]
        )
        with patch("temporalos.api.routes.intelligence.VideoAggregator", mock_cls):
            resp = self._tc.get("/api/v1/intelligence/objections")

        assert resp.status_code == 200
        data = resp.json()
        assert "objections" in data
        assert len(data["objections"]) == 2
        assert data["objections"][0]["text"] == "price is high"
        assert data["objections"][0]["count"] == 5

    def test_objections_endpoint_empty_result(self):
        mock_cls = self._mock_aggregator(top_objections=[])
        with patch("temporalos.api.routes.intelligence.VideoAggregator", mock_cls):
            resp = self._tc.get("/api/v1/intelligence/objections")

        assert resp.status_code == 200
        assert resp.json()["objections"] == []

    def test_objections_limit_query_param_forwarded(self):
        mock_cls = self._mock_aggregator(top_objections=[])
        with patch("temporalos.api.routes.intelligence.VideoAggregator", mock_cls) as patched:
            self._tc.get("/api/v1/intelligence/objections?limit=3")
        patched.return_value.top_objections.assert_awaited_once()
        call_kwargs = patched.return_value.top_objections.call_args.kwargs
        assert call_kwargs.get("limit") == 3

    # ── /intelligence/topics/trend ───────────────────────────────────────────

    def test_topics_trend_endpoint(self):
        mock_cls = self._mock_aggregator(
            topic_trends=[
                TopicTrend(topic="pricing", counts_by_day={"2026-03-01": 3}),
                TopicTrend(topic="features", counts_by_day={"2026-03-02": 1}),
            ]
        )
        with patch("temporalos.api.routes.intelligence.VideoAggregator", mock_cls):
            resp = self._tc.get("/api/v1/intelligence/topics/trend")

        assert resp.status_code == 200
        data = resp.json()
        assert "trends" in data
        assert len(data["trends"]) == 2
        topics = {t["topic"] for t in data["trends"]}
        assert "pricing" in topics

    def test_topics_trend_empty(self):
        mock_cls = self._mock_aggregator(topic_trends=[])
        with patch("temporalos.api.routes.intelligence.VideoAggregator", mock_cls):
            resp = self._tc.get("/api/v1/intelligence/topics/trend")
        assert resp.status_code == 200
        assert resp.json()["trends"] == []

    # ── /intelligence/risk/summary ───────────────────────────────────────────

    def test_risk_summary_endpoint(self):
        mock_cls = self._mock_aggregator(
            risk_summary=PortfolioRiskSummary(
                portfolio_id="all",
                video_count=10,
                avg_risk_score=0.62,
                high_risk_video_count=3,
                top_risk_topics=["pricing", "competition"],
            )
        )
        with patch("temporalos.api.routes.intelligence.VideoAggregator", mock_cls):
            resp = self._tc.get("/api/v1/intelligence/risk/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["video_count"] == 10
        assert data["avg_risk_score"] == pytest.approx(0.62)
        assert data["high_risk_video_count"] == 3
        assert "pricing" in data["top_risk_topics"]

    def test_risk_summary_empty_portfolio(self):
        mock_cls = self._mock_aggregator(
            risk_summary=PortfolioRiskSummary(
                portfolio_id="all",
                video_count=0,
                avg_risk_score=0.0,
                high_risk_video_count=0,
            )
        )
        with patch("temporalos.api.routes.intelligence.VideoAggregator", mock_cls):
            resp = self._tc.get("/api/v1/intelligence/risk/summary")

        assert resp.status_code == 200
        assert resp.json()["video_count"] == 0
