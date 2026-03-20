"""
Agreement metrics between multiple model runs — Phase 2 Observatory.

The Comparator takes a flat list of ModelRun objects (one per model per segment)
and produces a ComparisonReport with:
  - Per-model stats (latency, confidence, topic distribution)
  - Pairwise agreement matrices (topic, sentiment, risk)
  - Overall agreement score (mean of pairwise risk agreements)
  - Disagreement segments (where models give different risk levels)
"""

from __future__ import annotations

from collections import defaultdict

from .runner import ComparisonReport, ModelRun, ModelStats


class Comparator:
    """Compute agreement metrics across a list of ModelRun objects."""

    def compare(
        self,
        runs: list[ModelRun],
        session_id: str = "",
    ) -> ComparisonReport:
        if not runs:
            return ComparisonReport(session_id=session_id)

        # Group by segment timestamp
        by_segment: dict[int, list[ModelRun]] = defaultdict(list)
        for run in runs:
            by_segment[run.segment_timestamp_ms].append(run)

        model_names = sorted({r.model_name for r in runs})
        model_stats = {n: self._model_stats(n, runs) for n in model_names}

        # Build pairwise agreement matrices
        topic_agg: dict[str, dict[str, float]] = {}
        sentiment_agg: dict[str, dict[str, float]] = {}
        risk_agg: dict[str, dict[str, float]] = {}

        for i, m1 in enumerate(model_names):
            for m2 in model_names[i + 1 :]:
                ta, sa, ra = self._pairwise(by_segment, m1, m2)
                topic_agg.setdefault(m1, {})[m2] = ta
                topic_agg.setdefault(m2, {})[m1] = ta
                sentiment_agg.setdefault(m1, {})[m2] = sa
                sentiment_agg.setdefault(m2, {})[m1] = sa
                risk_agg.setdefault(m1, {})[m2] = ra
                risk_agg.setdefault(m2, {})[m1] = ra

        all_risk_vals = [v for d in risk_agg.values() for v in d.values()]
        overall = round(sum(all_risk_vals) / len(all_risk_vals), 3) if all_risk_vals else 1.0

        disagreements = sorted(
            ts for ts, seg_runs in by_segment.items()
            if self._has_risk_disagreement(seg_runs)
        )

        return ComparisonReport(
            session_id=session_id,
            segments_analyzed=len(by_segment),
            model_names=model_names,
            model_stats=model_stats,
            topic_agreement=topic_agg,
            sentiment_agreement=sentiment_agg,
            risk_agreement=risk_agg,
            overall_agreement=overall,
            disagreement_timestamps=disagreements,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _model_stats(self, model_name: str, runs: list[ModelRun]) -> ModelStats:
        model_runs = [r for r in runs if r.model_name == model_name]
        valid = [r for r in model_runs if r.extraction is not None]
        errors = [r for r in model_runs if r.error is not None]

        if not valid:
            return ModelStats(model_name=model_name, error_count=len(errors))

        latencies = [r.extraction.latency_ms for r in valid]  # type: ignore[union-attr]
        confidences = [r.extraction.confidence for r in valid]  # type: ignore[union-attr]
        risk_scores = [r.extraction.risk_score for r in valid]  # type: ignore[union-attr]

        topic_dist: dict[str, int] = {}
        for r in valid:
            t = r.extraction.topic  # type: ignore[union-attr]
            topic_dist[t] = topic_dist.get(t, 0) + 1

        return ModelStats(
            model_name=model_name,
            segments_processed=len(valid),
            error_count=len(errors),
            avg_latency_ms=round(sum(latencies) / len(latencies), 1),
            avg_confidence=round(sum(confidences) / len(confidences), 3),
            avg_risk_score=round(sum(risk_scores) / len(risk_scores), 3),
            topic_distribution=topic_dist,
        )

    def _pairwise(
        self,
        by_segment: dict[int, list[ModelRun]],
        m1: str,
        m2: str,
    ) -> tuple[float, float, float]:
        """Return (topic_agreement, sentiment_agreement, risk_agreement) for a model pair."""
        comparisons = 0
        topic_matches = sentiment_matches = risk_matches = 0

        for seg_runs in by_segment.values():
            r1 = next((r for r in seg_runs if r.model_name == m1 and r.extraction), None)
            r2 = next((r for r in seg_runs if r.model_name == m2 and r.extraction), None)
            if not r1 or not r2:
                continue
            comparisons += 1
            if r1.extraction.topic == r2.extraction.topic:  # type: ignore[union-attr]
                topic_matches += 1
            if r1.extraction.sentiment == r2.extraction.sentiment:  # type: ignore[union-attr]
                sentiment_matches += 1
            if r1.extraction.risk == r2.extraction.risk:  # type: ignore[union-attr]
                risk_matches += 1

        if comparisons == 0:
            return 1.0, 1.0, 1.0

        return (
            round(topic_matches / comparisons, 3),
            round(sentiment_matches / comparisons, 3),
            round(risk_matches / comparisons, 3),
        )

    def _has_risk_disagreement(self, seg_runs: list[ModelRun]) -> bool:
        risk_levels = {r.extraction.risk for r in seg_runs if r.extraction}
        return len(risk_levels) > 1
