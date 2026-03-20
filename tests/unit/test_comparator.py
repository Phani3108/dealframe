"""Unit tests — Observatory comparator agreement metrics."""

import pytest

from temporalos.core.types import ExtractionResult
from temporalos.observatory.comparator import Comparator
from temporalos.observatory.runner import ComparisonReport, ModelRun, ModelStats


def _run(model: str, ts: int, topic: str, sentiment: str, risk: str, risk_score: float = 0.5) -> ModelRun:
    return ModelRun(
        model_name=model,
        segment_timestamp_ms=ts,
        extraction=ExtractionResult(
            topic=topic,
            sentiment=sentiment,
            risk=risk,
            risk_score=risk_score,
            model_name=model,
            latency_ms=120,
            confidence=0.85,
        ),
    )


def _error_run(model: str, ts: int) -> ModelRun:
    return ModelRun(model_name=model, segment_timestamp_ms=ts, error="API timeout")


class TestComparatorAgreement:
    def test_empty_runs_returns_empty_report(self):
        report = Comparator().compare([], session_id="s0")
        assert report.session_id == "s0"
        assert report.segments_analyzed == 0
        assert report.model_names == []

    def test_single_model_no_pairwise(self):
        runs = [_run("gpt4o", 0, "pricing", "hesitant", "high")]
        report = Comparator().compare(runs)
        assert report.model_names == ["gpt4o"]
        assert report.topic_agreement == {}
        assert report.overall_agreement == 1.0  # no pairs → default 1.0

    def test_perfect_agreement(self):
        data = [
            (0, "pricing", "hesitant", "high"),
            (2000, "features", "positive", "low"),
        ]
        runs = (
            [_run("m1", ts, t, s, r) for ts, t, s, r in data]
            + [_run("m2", ts, t, s, r) for ts, t, s, r in data]
        )
        report = Comparator().compare(runs, session_id="perfect")
        assert report.overall_agreement == 1.0
        assert report.disagreement_timestamps == []
        assert report.risk_agreement["m1"]["m2"] == 1.0

    def test_full_topic_disagreement(self):
        runs = [
            _run("m1", 0, "pricing", "hesitant", "high", 0.8),
            _run("m2", 0, "features", "positive", "low", 0.2),
        ]
        report = Comparator().compare(runs)
        assert report.topic_agreement["m1"]["m2"] == 0.0
        assert report.risk_agreement["m1"]["m2"] == 0.0
        assert len(report.disagreement_timestamps) == 1
        assert report.overall_agreement == 0.0

    def test_partial_agreement(self):
        # Segment 0: agree on risk; Segment 2000: disagree
        runs = [
            _run("m1", 0, "pricing", "hesitant", "high"),
            _run("m2", 0, "pricing", "hesitant", "high"),  # agree
            _run("m1", 2000, "pricing", "hesitant", "high"),
            _run("m2", 2000, "features", "positive", "low"),  # disagree
        ]
        report = Comparator().compare(runs)
        assert report.risk_agreement["m1"]["m2"] == 0.5
        assert report.disagreement_timestamps == [2000]
        assert 0.0 < report.overall_agreement < 1.0

    def test_error_runs_excluded_from_agreement(self):
        runs = [
            _run("m1", 0, "pricing", "hesitant", "high"),
            _error_run("m2", 0),
        ]
        report = Comparator().compare(runs)
        # m2 has no extraction on segment 0 → no comparison possible → defaults to 1.0
        assert report.risk_agreement.get("m1", {}).get("m2", 1.0) == 1.0
        assert report.model_stats["m2"].error_count == 1

    def test_model_stats_populated(self):
        runs = [
            _run("gpt4o", 0, "pricing", "hesitant", "high", 0.8),
            _run("gpt4o", 2000, "features", "positive", "low", 0.2),
        ]
        report = Comparator().compare(runs)
        stats = report.model_stats["gpt4o"]
        assert stats.segments_processed == 2
        assert stats.error_count == 0
        assert stats.avg_confidence == pytest.approx(0.85)
        assert stats.avg_risk_score == pytest.approx(0.5)
        assert "pricing" in stats.topic_distribution
        assert "features" in stats.topic_distribution

    def test_to_dict_shape(self):
        runs = [
            _run("m1", 0, "pricing", "hesitant", "high"),
            _run("m2", 0, "pricing", "hesitant", "high"),
        ]
        report = Comparator().compare(runs, session_id="dict_test")
        d = report.to_dict()

        assert d["session_id"] == "dict_test"
        assert "segments_analyzed" in d
        assert "model_names" in d
        assert "model_stats" in d
        assert "pairwise_agreement" in d
        assert "overall" in d["pairwise_agreement"]
        assert "disagreement_count" in d

    def test_symmetric_pairwise_matrices(self):
        runs = [
            _run("alpha", 0, "pricing", "hesitant", "high"),
            _run("beta", 0, "features", "positive", "low"),
        ]
        report = Comparator().compare(runs)
        ta = report.topic_agreement.get("alpha", {}).get("beta")
        tb = report.topic_agreement.get("beta", {}).get("alpha")
        assert ta == tb  # matrices must be symmetric
