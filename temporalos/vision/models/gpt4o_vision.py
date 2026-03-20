"""GPT-4o Vision frame analysis adapter — standalone frame intelligence."""

from __future__ import annotations

import base64
import json
import time

from openai import OpenAI
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


class GPT4oVisionModel(BaseVisionModel):
    name = "gpt4o_vision"

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @classmethod
    def from_settings(cls) -> "GPT4oVisionModel":
        from ...config import get_settings

        s = get_settings()
        return cls(model=s.openai.vision_model, api_key=s.openai_api_key or None)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def analyze_frame(self, frame: Frame) -> FrameAnalysis:
        tracer = get_tracer()
        with tracer.start_as_current_span("vision.gpt4o") as span:
            span.set_attribute("vision.model", self.name)
            span.set_attribute("vision.timestamp_ms", frame.timestamp_ms)

            t0 = time.monotonic()
            with open(frame.path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}",
                                    "detail": "low",
                                },
                            },
                            {
                                "type": "text",
                                "text": "Analyse this frame from a sales call recording.",
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=512,
            )

            latency_ms = int((time.monotonic() - t0) * 1000)
            data = json.loads(response.choices[0].message.content or "{}")

            return FrameAnalysis(
                frame_type=data.get("frame_type", "other"),
                ocr_text=data.get("ocr_text", ""),
                objects=data.get("objects", []),
                confidence=float(data.get("confidence", 0.0)),
                model_name=self.name,
                latency_ms=latency_ms,
            )
