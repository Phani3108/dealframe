"""GPT-4o extraction adapter — uses vision + text for structured output."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ...core.types import AlignedSegment, ExtractionResult
from ...observability.telemetry import get_tracer
from ..base import BaseExtractionModel

# ── Prompt & Schema ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a sales intelligence analyst. Given a segment from a sales call \
(optional screenshot + transcript), extract structured decision intelligence.
Be precise and evidence-based. Only include objections and decision signals \
that are clearly stated or strongly implied in the provided content.
Respond ONLY with valid JSON — no prose, no markdown fences.\
"""

_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {
            "type": "string",
            "description": (
                "Primary topic: pricing | features | competition | timeline | "
                "security | onboarding | support | legal | other"
            ),
        },
        "sentiment": {
            "type": "string",
            "enum": ["positive", "neutral", "negative", "hesitant"],
        },
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "risk_score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Numeric deal-risk score (0 = no risk, 1 = high risk)",
        },
        "objections": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Verbatim or close-paraphrase objections raised",
        },
        "decision_signals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Signals that indicate buying intent or next steps",
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Model's confidence in the extraction (0–1)",
        },
    },
    "required": [
        "topic", "sentiment", "risk", "risk_score",
        "objections", "decision_signals", "confidence",
    ],
}

_USER_TEMPLATE = """\
Timestamp: {timestamp}

Transcript:
{transcript}

{ocr_block}Extract structured intelligence matching this JSON schema:
{schema}
"""


def _format_ocr_block(ocr_text: str, frame_type: str) -> str:
    """Render the on-screen text block for the LLM prompt when available."""
    ocr_text = (ocr_text or "").strip()
    if not ocr_text:
        return ""
    ft = f" ({frame_type})" if frame_type else ""
    return (
        f"On-screen text{ft} (from slide/screen OCR — use as evidence when it disambiguates the transcript):\n"
        f"{ocr_text}\n\n"
    )


# ── Adapter ────────────────────────────────────────────────────────────────────

class GPT4oExtractionModel(BaseExtractionModel):
    name = "gpt4o"

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        max_tokens: int = 512,
    ) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    @classmethod
    def from_settings(cls) -> "GPT4oExtractionModel":
        from ...config import get_settings

        s = get_settings()
        return cls(
            model=s.openai.model,
            api_key=s.openai_api_key or None,
            max_tokens=s.openai.max_tokens,
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        tracer = get_tracer()
        with tracer.start_as_current_span("extraction.gpt4o") as span:
            span.set_attribute("extraction.model", self.name)
            span.set_attribute("extraction.timestamp_ms", segment.timestamp_ms)
            span.set_attribute("extraction.word_count", len(segment.words))

            t0 = time.monotonic()
            messages = self._build_messages(segment)

            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=self._max_tokens,
            )

            latency_ms = int((time.monotonic() - t0) * 1000)
            span.set_attribute("extraction.latency_ms", latency_ms)

            raw = response.choices[0].message.content or "{}"
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

    def _build_messages(self, segment: AlignedSegment) -> list[dict]:
        user_parts: list[dict] = []

        if segment.frame and Path(segment.frame.path).exists():
            with open(segment.frame.path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            user_parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                        "detail": "low",  # lower cost; use "high" for detailed OCR
                    },
                }
            )

        user_parts.append(
            {
                "type": "text",
                "text": _USER_TEMPLATE.format(
                    timestamp=segment.timestamp_str,
                    transcript=segment.transcript or "(no speech in this segment)",
                    ocr_block=_format_ocr_block(
                        getattr(segment, "ocr_text", ""),
                        getattr(segment, "frame_type", ""),
                    ),
                    schema=json.dumps(_EXTRACTION_SCHEMA, indent=2),
                ),
            }
        )

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_parts},
        ]
