"""Prometheus metrics registry for DealFrame pipeline telemetry."""

from __future__ import annotations

import threading
from typing import Optional

# Lazy import so the app starts normally even without prometheus_client installed
try:
    from prometheus_client import (  # type: ignore[import]
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

_registry_lock = threading.Lock()
_metrics: Optional["PipelineMetrics"] = None


class PipelineMetrics:
    """Singleton holder for all Prometheus metric objects."""

    def __init__(self) -> None:
        if not _PROMETHEUS_AVAILABLE:
            self._available = False
            return

        self._available = True
        self.registry = CollectorRegistry()

        self.extractions_total = Counter(
            "temporalos_extractions_total",
            "Total extraction calls",
            ["model", "risk"],
            registry=self.registry,
        )
        self.extraction_errors_total = Counter(
            "temporalos_extraction_errors_total",
            "Total extraction failures",
            ["model"],
            registry=self.registry,
        )
        self.extraction_confidence = Histogram(
            "temporalos_extraction_confidence",
            "Extraction confidence score distribution",
            ["model"],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=self.registry,
        )
        self.stage_latency_ms = Histogram(
            "temporalos_stage_latency_ms",
            "Pipeline stage latency in milliseconds",
            ["stage"],
            buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
            registry=self.registry,
        )
        self.cost_usd = Counter(
            "temporalos_cost_usd_total",
            "Cumulative API cost in USD",
            ["model"],
            registry=self.registry,
        )
        self.videos_processed_total = Counter(
            "temporalos_videos_processed_total",
            "Total videos processed",
            ["status"],
            registry=self.registry,
        )
        self.active_jobs = Gauge(
            "temporalos_active_jobs",
            "Currently processing jobs",
            registry=self.registry,
        )

    @property
    def available(self) -> bool:
        return self._available

    def record_extraction(
        self,
        model: str,
        risk: str,
        confidence: float,
        latency_ms: int,
        cost_usd: float = 0.0,
    ) -> None:
        if not self._available:
            return
        self.extractions_total.labels(model=model, risk=risk).inc()
        self.extraction_confidence.labels(model=model).observe(confidence)
        self.stage_latency_ms.labels(stage=f"extraction.{model}").observe(latency_ms)
        if cost_usd > 0:
            self.cost_usd.labels(model=model).inc(cost_usd)

    def record_error(self, model: str) -> None:
        if not self._available:
            return
        self.extraction_errors_total.labels(model=model).inc()

    def record_stage(self, stage: str, latency_ms: int) -> None:
        if not self._available:
            return
        self.stage_latency_ms.labels(stage=stage).observe(latency_ms)

    def record_video(self, status: str) -> None:
        if not self._available:
            return
        self.videos_processed_total.labels(status=status).inc()

    def render_prometheus(self) -> tuple[bytes, str]:
        """Return (body_bytes, content_type) for the /metrics endpoint."""
        if not self._available:
            return b"# prometheus_client not installed\n", "text/plain"
        return generate_latest(self.registry), CONTENT_TYPE_LATEST


def get_metrics() -> PipelineMetrics:
    global _metrics
    with _registry_lock:
        if _metrics is None:
            _metrics = PipelineMetrics()
    return _metrics
