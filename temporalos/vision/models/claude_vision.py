"""Claude Vision frame analysis adapter — standalone frame intelligence."""

from __future__ import annotations

import base64
import json
import time

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ...core.types import Frame
from ...observability.telemetry import get_tracer
from ..base import BaseVisionModel, FrameAnalysis

_SYSTEM = """\
You are a video frame analyst for a sales intelligence system.
Analyse the given frame captured from a sales call or product demo recording.
Respond ONLY with valid JSON — no prose, no markdown fences.
JSON schema:
{
  "frame_type": "slide | face | screen | chart | whiteboard | other",
  "ocr_text": "all visible text in the frame",
  "objects": ["list of detected visual elements"],
  "confidence": 0.0
}\
"""

_USER = "Analyse this frame from a sales call recording."


class ClaudeVisionModel(BaseVisionModel):
    name = "claude_vision"

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        api_key: str | None = None,
    ) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model

    @classmethod
    def from_settings(cls) -> "ClaudeVisionModel":
        from ...config import get_settings

        s = get_settings()
        return cls(model=s.anthropic.vision_model, api_key=s.anthropic_api_key or None)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def analyze_frame(self, frame: Frame) -> FrameAnalysis:
        tracer = get_tracer()
        with tracer.start_as_current_span("vision.claude") as span:
            span.set_attribute("vision.model", self.name)
            span.set_attribute("vision.timestamp_ms", frame.timestamp_ms)

            t0 = time.monotonic()
            with open(frame.path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                system=_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": img_b64,
                                },
                            },
                            {"type": "text", "text": _USER},
                        ],
                    }
                ],
            )

            latency_ms = int((time.monotonic() - t0) * 1000)
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                raw = raw[4:].strip() if raw.startswith("json") else raw.strip()

            data: dict = json.loads(raw)

            return FrameAnalysis(
                frame_type=data.get("frame_type", "other"),
                ocr_text=data.get("ocr_text", ""),
                objects=data.get("objects", []),
                confidence=float(data.get("confidence", 0.0)),
                model_name=self.name,
                latency_ms=latency_ms,
            )
