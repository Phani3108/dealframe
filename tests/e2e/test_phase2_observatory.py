"""
Phase 2 end-to-end test — Comparative Model Observatory.

Tests the full observatory pipeline:
  aligned segments → parallel multi-model extraction → agreement comparison → JSON report

Rules (from claude.md §0):
  - Uses sample_segments fixture (no external video required)
  - All external API calls (OpenAI, Anthropic) are mocked
  - No real DB required — observatory uses in-memory session store
  - Tests ObservatoryRunner, Comparator, and the /observatory/* API routes
  - Must pass with 0 failures before Phase 2 is "done"
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from temporalos.core.types import AlignedSegment, ExtractionResult
from temporalos.observatory.comparator import Comparator
from temporalos.observatory.runner import ComparisonReport, ModelRun, ObservatoryRunner


# ── Mock helpers ───────────────────────────────────────────────────────────────


class _InfallibleModel:
    """Extraction model that always returns deterministic results — no API calls."""

    def __init__(
        self,
        name: str,
        topic: str = "pricing",
        sentiment: str = "hesitant",
        risk: str = "high",
        risk_score: float = 0.75,
    ) -> None:
        self.name = name
        self._topic = topic
        self._sentiment = sentiment
        self._risk = risk
        self._risk_score = risk_score

    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        return ExtractionResult(
            topic=self._topic,
            sentiment=self._sentiment,
            risk=self._risk,
            risk_score=self._risk_score,
            objections=["Price concern"],
            decision_signals=["Request for proposal"],
            confidence=0.9,
            model_name=self.name,
            latency_ms=42,
        )

    def extract_batch(self, segments: list) -> list:
        return [self.extract(s) for s in segments]


class _BrokenModel:
    """Always raises an exception — tests error isolation."""

    name = "broken_model"

    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        raise RuntimeError("Simulated API failure")

    def extract_batch(self, segments: list) -> list:
        return [self.extract(s) for s in segments]


# ── ObservatoryRunner ──────────────────────────────────────────────────────────


class TestObservatoryRunner:
    def test_run_produces_one_run_per_model_per_segment(self, sample_segments):
        non_empty = [s for s in sample_segments if s.words]
        runner = ObservatoryRunner(max_workers=2)
        runner.register_extractor(_InfallibleModel("gpt4o"))
        runner.register_extractor(_InfallibleModel("claude"))

        runs = runner.run(sample_segments)

        assert len(runs) == len(non_empty) * 2
        assert {r.model_name for r in runs} == {"gpt4o", "claude"}

    def test_run_captures_model_errors(self, sample_segments):
        runner = ObservatoryRunner()
        runner.register_extractor(_BrokenModel())

        runs = runner.run(sample_segments)

        assert all(r.error is not None for r in runs)
        assert all(r.extraction is None for r in runs)

    def test_run_empty_segments_returns_empty(self):
        runner = ObservatoryRunner()
        runner.register_extractor(_InfallibleModel("m"))
        assert runner.run([]) == []

    def test_run_skips_silent_segments(self, sample_frames):
        """Segments with no words are excluded from model runs."""
        silent = [AlignedSegment(timestamp_ms=i * 2000, frame=f, words=[]) for i, f in enumerate(sample_frames)]
        runner = ObservatoryRunner()
        runner.register_extractor(_InfallibleModel("m"))
        assert runner.run(silent) == []

    def test_compare_delegates_to_comparator(self, sample_segments):
        runner = ObservatoryRunner()
        runner.register_extractor(_InfallibleModel("m1"))
        runner.register_extractor(_InfallibleModel("m2", topic="features"))

        runs = runner.run(sample_segments)
        report = runner.compare(runs)

        assert isinstance(report, ComparisonReport)
        assert report.session_id != ""
        assert len(report.model_names) == 2


# ── Comparator ────────────────────────────────────────────────────────────────


class TestComparatorE2E:
    """Integration-level tests — build ModelRun lists and verify report shape."""

    def _build_runs(
        self,
        model_a_kwargs: dict,
        model_b_kwargs: dict,
        n_segments: int = 3,
    ) -> list[ModelRun]:
        runs = []
        for i in range(n_segments):
            ts = i * 2000
            for kwargs in (model_a_kwargs, model_b_kwargs):
                ext = ExtractionResult(
                    topic=kwargs.get("topic", "pricing"),
                    sentiment=kwargs.get("sentiment", "hesitant"),
                    risk=kwargs.get("risk", "high"),
                    risk_score=kwargs.get("risk_score", 0.7),
                    objections=[],
                    decision_signals=[],
                    confidence=0.9,
                    model_name=kwargs["name"],
                    latency_ms=50,
                )
                runs.append(ModelRun(
                    model_name=kwargs["name"],
                    segment_timestamp_ms=ts,
                    extraction=ext,
                ))
        return runs

    def test_identical_models_produce_perfect_agreement(self):
        runs = self._build_runs(
            {"name": "m1", "topic": "pricing", "sentiment": "hesitant", "risk": "high"},
            {"name": "m2", "topic": "pricing", "sentiment": "hesitant", "risk": "high"},
        )
        report = Comparator().compare(runs, session_id="e2e_perfect")

        assert report.overall_agreement == 1.0
        assert report.disagreement_timestamps == []
        assert report.model_stats["m1"].segments_processed == 3

    def test_fully_divergent_models_produce_zero_agreement(self):
        runs = self._build_runs(
            {"name": "m1", "topic": "pricing", "sentiment": "hesitant", "risk": "high"},
            {"name": "m2", "topic": "features", "sentiment": "positive", "risk": "low"},
        )
        report = Comparator().compare(runs, session_id="e2e_diverge")

        assert report.overall_agreement == 0.0
        assert len(report.disagreement_timestamps) == 3

    def test_report_to_dict_is_json_serialisable(self, sample_segments):
        runner = ObservatoryRunner()
        runner.register_extractor(_InfallibleModel("m1"))
        runner.register_extractor(_InfallibleModel("m2", topic="features", risk="low", risk_score=0.2))

        runs = runner.run(sample_segments)
        report = runner.compare(runs, "json_test")

        raw = json.dumps(report.to_dict())  # must not raise
        data = json.loads(raw)

        assert "session_id" in data
        assert "model_names" in data
        assert "model_stats" in data
        assert "pairwise_agreement" in data
        assert "overall" in data["pairwise_agreement"]

    def test_error_runs_not_counted_in_stats(self):
        runs = [
            ModelRun("m1", 0, extraction=ExtractionResult("pricing", "hesitant", "high", 0.8, [], [], 0.9, "m1", 40)),
            ModelRun("m1", 2000, error="API error"),
            ModelRun("m2", 0, extraction=ExtractionResult("pricing", "hesitant", "high", 0.8, [], [], 0.9, "m2", 40)),
            ModelRun("m2", 2000, extraction=ExtractionResult("features", "positive", "low", 0.2, [], [], 0.7, "m2", 40)),
        ]
        report = Comparator().compare(runs, "err_test")

        assert report.model_stats["m1"].segments_processed == 1
        assert report.model_stats["m1"].error_count == 1


# ── Observatory API ────────────────────────────────────────────────────────────


class TestObservatoryAPI:
    """
    Tests the /observatory/* REST endpoints.
    The full video pipeline is bypassed — _run_observatory is swapped for a function
    that immediately populates the session store with a synthetic completed report.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, test_video_path):
        self._video_path = test_video_path

        _synthetic_report = {
            "session_id": "test_session",
            "segments_analyzed": 3,
            "model_names": ["gpt4o", "claude"],
            "model_stats": {
                "gpt4o": {"model_name": "gpt4o", "segments_processed": 3, "error_count": 0,
                           "avg_latency_ms": 45.0, "avg_confidence": 0.88, "avg_risk_score": 0.7,
                           "topic_distribution": {"pricing": 3}},
                "claude": {"model_name": "claude", "segments_processed": 3, "error_count": 0,
                            "avg_latency_ms": 55.0, "avg_confidence": 0.85, "avg_risk_score": 0.65,
                            "topic_distribution": {"pricing": 2, "features": 1}},
            },
            "pairwise_agreement": {
                "topic": {"gpt4o": {"claude": 0.667}, "claude": {"gpt4o": 0.667}},
                "sentiment": {"gpt4o": {"claude": 1.0}, "claude": {"gpt4o": 1.0}},
                "risk": {"gpt4o": {"claude": 1.0}, "claude": {"gpt4o": 1.0}},
                "overall": 1.0,
            },
            "disagreement_count": 0,
            "disagreement_timestamps_ms": [],
        }

        def _fake_runner(session_id: str, video_path: str, frames_dir: str) -> None:
            from temporalos.api.routes.observatory import _sessions
            _sessions[session_id]["status"] = "completed"
            _sessions[session_id]["report"] = _synthetic_report
            _sessions[session_id]["total_runs"] = 6

        self._fake_runner = _fake_runner

    def _make_client(self):
        with patch("temporalos.db.session.init_db", return_value=None):
            from temporalos.api.main import app
            return TestClient(app, raise_server_exceptions=True)

    def test_compare_returns_202_with_session_id(self):
        client = self._make_client()

        with patch("temporalos.api.routes.observatory._run_observatory", side_effect=self._fake_runner):
            with open(self._video_path, "rb") as f:
                resp = client.post(
                    "/api/v1/observatory/compare",
                    files={"file": ("test.mp4", f, "video/mp4")},
                )

        assert resp.status_code == 202
        body = resp.json()
        assert "session_id" in body
        assert body["status"] == "pending"

    def test_poll_completed_session_returns_report(self):
        client = self._make_client()

        with patch("temporalos.api.routes.observatory._run_observatory", side_effect=self._fake_runner):
            with open(self._video_path, "rb") as f:
                submit = client.post(
                    "/api/v1/observatory/compare",
                    files={"file": ("test.mp4", f, "video/mp4")},
                )
        session_id = submit.json()["session_id"]

        poll = client.get(f"/api/v1/observatory/sessions/{session_id}")
        assert poll.status_code == 200
        data = poll.json()
        assert data["status"] == "completed"
        assert "report" in data
        assert data["report"]["segments_analyzed"] == 3
        assert len(data["report"]["model_names"]) == 2

    def test_poll_unknown_session_returns_404(self):
        client = self._make_client()
        resp = client.get("/api/v1/observatory/sessions/does-not-exist")
        assert resp.status_code == 404

    def test_unsupported_format_rejected(self):
        client = self._make_client()
        resp = client.post(
            "/api/v1/observatory/compare",
            files={"file": ("video.xyz", BytesIO(b"data"), "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_list_sessions_returns_all(self):
        client = self._make_client()

        with patch("temporalos.api.routes.observatory._run_observatory", side_effect=self._fake_runner):
            for _ in range(2):
                with open(self._video_path, "rb") as f:
                    client.post(
                        "/api/v1/observatory/compare",
                        files={"file": ("test.mp4", f, "video/mp4")},
                    )

        resp = client.get("/api/v1/observatory/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert data["total"] >= 2
