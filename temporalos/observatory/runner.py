"""
Observatory runner — Phase 2: Comparative Model Observatory.

Runs the same video segments through multiple extraction (and optionally vision)
model adapters in parallel, then computes pairwise agreement reports.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.types import AlignedSegment, ExtractionResult
    from ..vision.base import BaseVisionModel, FrameAnalysis
    from ..extraction.base import BaseExtractionModel


@dataclass
class ModelRun:
    """Single model result on a single aligned segment."""

    model_name: str
    segment_timestamp_ms: int
    extraction: "ExtractionResult | None" = None
    vision: "FrameAnalysis | None" = None
    error: str | None = None


@dataclass
class ModelStats:
    """Per-model aggregate stats over all segments in a session."""

    model_name: str
    segments_processed: int = 0
    error_count: int = 0
    avg_latency_ms: float = 0.0
    avg_confidence: float = 0.0
    avg_risk_score: float = 0.0
    topic_distribution: dict[str, int] = field(default_factory=dict)


@dataclass
class ComparisonReport:
    """
    Pairwise agreement metrics across all registered models.

    Matrices are keyed as {model_a: {model_b: score_0_to_1}}.
    overall_agreement is the mean pairwise risk agreement.
    """

    session_id: str = ""
    segments_analyzed: int = 0
    model_names: list[str] = field(default_factory=list)
    model_stats: dict[str, ModelStats] = field(default_factory=dict)
    topic_agreement: dict[str, dict[str, float]] = field(default_factory=dict)
    sentiment_agreement: dict[str, dict[str, float]] = field(default_factory=dict)
    risk_agreement: dict[str, dict[str, float]] = field(default_factory=dict)
    overall_agreement: float = 0.0
    disagreement_timestamps: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "segments_analyzed": self.segments_analyzed,
            "model_names": self.model_names,
            "model_stats": {k: vars(v) for k, v in self.model_stats.items()},
            "pairwise_agreement": {
                "topic": self.topic_agreement,
                "sentiment": self.sentiment_agreement,
                "risk": self.risk_agreement,
                "overall": self.overall_agreement,
            },
            "disagreement_count": len(self.disagreement_timestamps),
            "disagreement_timestamps_ms": self.disagreement_timestamps,
        }


class ObservatoryRunner:
    """
    Comparative Model Observatory — Phase 2.

    Registers vision and extraction model adapters, then runs all of them over
    the same set of segments in parallel (ThreadPoolExecutor), collecting
    ModelRun results for comparison via the Comparator.

    Usage:
        runner = ObservatoryRunner()
        runner.register_extractor(GPT4oExtractionModel.from_settings())
        runner.register_extractor(ClaudeExtractionModel.from_settings())

        runs = runner.run(segments)
        report = runner.compare(runs)   # delegates to Comparator
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._extractors: list["BaseExtractionModel"] = []
        self._vision_models: list["BaseVisionModel"] = []
        self._max_workers = max_workers

    def register_extractor(self, model: "BaseExtractionModel") -> None:
        self._extractors.append(model)

    def register_vision_model(self, model: "BaseVisionModel") -> None:
        self._vision_models.append(model)

    def run(self, segments: "list[AlignedSegment]") -> list[ModelRun]:
        """
        Run all registered extraction models in parallel across all non-empty segments.
        Returns every ModelRun (one per model per non-empty segment).
        """
        from ..observability.telemetry import get_tracer

        tracer = get_tracer()
        non_empty = [s for s in segments if s.words]

        if not self._extractors or not non_empty:
            return []

        with tracer.start_as_current_span("observatory.run") as span:
            span.set_attribute("observatory.model_count", len(self._extractors))
            span.set_attribute("observatory.segment_count", len(non_empty))

            runs: list[ModelRun] = []
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {
                    pool.submit(self._run_single, model, seg): (model.name, seg.timestamp_ms)
                    for model in self._extractors
                    for seg in non_empty
                }
                for future in as_completed(futures):
                    runs.append(future.result())

            span.set_attribute("observatory.runs_completed", len(runs))
            return runs

    def _run_single(
        self,
        model: "BaseExtractionModel",
        segment: "AlignedSegment",
    ) -> ModelRun:
        try:
            result = model.extract(segment)
            return ModelRun(
                model_name=model.name,
                segment_timestamp_ms=segment.timestamp_ms,
                extraction=result,
            )
        except Exception as exc:
            return ModelRun(
                model_name=model.name,
                segment_timestamp_ms=segment.timestamp_ms,
                error=str(exc),
            )

    def compare(self, runs: list[ModelRun], session_id: str = "") -> ComparisonReport:
        """Convenience — delegates to Comparator."""
        from .comparator import Comparator

        sid = session_id or str(uuid.uuid4())
        return Comparator().compare(runs, session_id=sid)
