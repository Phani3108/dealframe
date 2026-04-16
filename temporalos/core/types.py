"""Core shared data types used across all pipeline stages."""

from dataclasses import dataclass, field


@dataclass
class Frame:
    """A single extracted video frame with its source timestamp."""

    path: str
    timestamp_ms: int

    @property
    def timestamp_str(self) -> str:
        total = self.timestamp_ms // 1000
        return f"{total // 60:02d}:{total % 60:02d}"


@dataclass
class Word:
    """A single transcribed word with precise timing and optional speaker label."""

    text: str
    start_ms: int
    end_ms: int
    speaker: str | None = None


@dataclass
class AlignedSegment:
    """
    A time-window that combines a video frame with the words spoken during that window.
    This is the fundamental unit passed to extraction models.
    """

    timestamp_ms: int
    frame: Frame | None
    words: list[Word]
    # Optional OCR text extracted from the frame by the VisionPipeline.
    # When present, extraction models should include it as additional context.
    ocr_text: str = ""
    frame_type: str = ""

    @property
    def timestamp_str(self) -> str:
        total = self.timestamp_ms // 1000
        return f"{total // 60:02d}:{total % 60:02d}"

    @property
    def transcript(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def duration_ms(self) -> int:
        if not self.words:
            return 0
        return self.words[-1].end_ms - self.words[0].start_ms


@dataclass
class ExtractionResult:
    """Structured intelligence extracted from a single aligned segment."""

    topic: str
    sentiment: str  # positive | neutral | negative | hesitant
    risk: str  # low | medium | high
    risk_score: float  # 0.0 – 1.0
    objections: list[str] = field(default_factory=list)
    decision_signals: list[str] = field(default_factory=list)
    confidence: float = 0.0
    model_name: str = ""
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "customer_sentiment": self.sentiment,
            "risk": self.risk,
            "risk_score": self.risk_score,
            "objections": self.objections,
            "decision_signals": self.decision_signals,
            "confidence": self.confidence,
            "model": self.model_name,
        }


@dataclass
class VideoIntelligence:
    """Full structured output for a processed video."""

    video_path: str
    duration_ms: int
    segments: list[tuple[AlignedSegment, ExtractionResult]]

    @property
    def overall_risk_score(self) -> float:
        if not self.segments:
            return 0.0
        return sum(e.risk_score for _, e in self.segments) / len(self.segments)

    def to_dict(self) -> dict:
        return {
            "segments": [
                {"timestamp": seg.timestamp_str, **ext.to_dict()}
                for seg, ext in self.segments
            ],
            "overall_risk_score": round(self.overall_risk_score, 2),
        }
