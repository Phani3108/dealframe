"""Claude Sonnet extraction adapter."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ...core.types import AlignedSegment, ExtractionResult
from ...observability.telemetry import get_tracer
from ..base import BaseExtractionModel

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM = """\
You are a sales intelligence analyst. Given a segment from a sales call \
(optional screenshot + transcript), extract structured decision intelligence.
Be precise and evidence-based. Only include objections and decision signals \
that are clearly stated or strongly implied.
Respond ONLY with valid JSON — no prose, no markdown fences.\
"""

_USER_TEMPLATE = """\
Timestamp: {timestamp}

Transcript:
{transcript}

Extract structured intelligence as JSON with these fields:
- topic: pricing | features | competition | timeline | security | onboarding | support | legal | other
- sentiment: positive | neutral | negative | hesitant
- risk: low | medium | high
- risk_score: number 0.0-1.0
- objections: array of quoted strings
- decision_signals: array of quoted strings
- confidence: number 0.0-1.0\
"""


# ── Adapter ────────────────────────────────────────────────────────────────────

class ClaudeExtractionModel(BaseExtractionModel):
    name = "claude"

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        api_key: str | None = None,
        max_tokens: int = 512,
    ) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    @classmethod
    def from_settings(cls) -> "ClaudeExtractionModel":
        from ...config import get_settings

        s = get_settings()
        return cls(
            model=s.anthropic.model,
            api_key=s.anthropic_api_key or None,
            max_tokens=s.anthropic.max_tokens,
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        tracer = get_tracer()
        with tracer.start_as_current_span("extraction.claude") as span:
            span.set_attribute("extraction.model", self.name)
            span.set_attribute("extraction.timestamp_ms", segment.timestamp_ms)
            span.set_attribute("extraction.word_count", len(segment.words))

            t0 = time.monotonic()
            content = self._build_content(segment)

            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_SYSTEM,
                messages=[{"role": "user", "content": content}],
            )

            latency_ms = int((time.monotonic() - t0) * 1000)
            span.set_attribute("extraction.latency_ms", latency_ms)

            raw = response.content[0].text.strip()
            # Strip markdown code fences if the model includes them
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                raw = raw[4:].strip() if raw.startswith("json") else raw.strip()

            data: dict = json.loads(raw)

            return ExtractionResult(
                topic=data.get("topic", "other"),
                sentiment=data.get("sentiment", "neutral"),
                risk=data.get("risk", "low"),
                risk_score=float(data.get("risk_score", 0.0)),
                objections=data.get("objections", []),
                decision_signals=data.get("decision_signals", []),
                confidence=float(data.get("confidence", 0.0)),
                model_name=self.name,
                latency_ms=latency_ms,
            )

    def _build_content(self, segment: AlignedSegment) -> list[dict]:
        content: list[dict] = []

        if segment.frame and Path(segment.frame.path).exists():
            with open(segment.frame.path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_b64,
                },
            })

        content.append({
            "type": "text",
            "text": _USER_TEMPLATE.format(
                timestamp=segment.timestamp_str,
                transcript=segment.transcript or "(no speech in this segment)",
            ),
        })
        return content
