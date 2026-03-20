"""
Qwen2.5-VL local frame analysis adapter — zero API calls.

Requires the vision extras:
    pip install -e '.[vision]'

Designed to run on:
  - Apple Silicon (M-series) with MPS or CPU in 4-bit quantization
  - CUDA GPU with float16
  - CPU fallback (slow but functional)
"""

from __future__ import annotations

import time
from pathlib import Path

from ...core.types import Frame
from ...observability.telemetry import get_tracer
from ..base import BaseVisionModel, FrameAnalysis

_MODEL_CACHE: dict[str, object] = {}

_PROMPT = """\
Analyse this video frame from a sales call recording.
Respond ONLY with valid JSON:
{
  "frame_type": "slide | face | screen | chart | whiteboard | other",
  "ocr_text": "all visible text",
  "objects": ["detected visual elements"],
  "confidence": 0.0
}\
"""


def _load_model(model_id: str) -> tuple:
    """Lazy-load Qwen2.5-VL model and processor. Cached after first load."""
    if model_id in _MODEL_CACHE:
        return _MODEL_CACHE[model_id]  # type: ignore[return-value]

    try:
        import torch
        from transformers import AutoProcessor
        from qwen_vl_utils import process_vision_info  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "Qwen2.5-VL requires the vision extras:\n"
            "    pip install -e '.[vision]'\n"
            f"Missing: {exc}"
        ) from exc

    # Try to import the specific model class
    try:
        from transformers import Qwen2_5_VLForConditionalGeneration  # type: ignore[import]
    except ImportError:
        from transformers import AutoModelForVision2Seq as Qwen2_5_VLForConditionalGeneration  # type: ignore[import]

    device = (
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )
    dtype = torch.float16 if device in ("cuda", "mps") else torch.float32

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=dtype,
        device_map="auto",
        load_in_4bit=True,  # 4-bit quantization → fits in 16 GB RAM
    )
    processor = AutoProcessor.from_pretrained(model_id)

    _MODEL_CACHE[model_id] = (model, processor, process_vision_info, device)
    return model, processor, process_vision_info, device


class QwenVLModel(BaseVisionModel):
    """
    Qwen2.5-VL-7B-Instruct as a drop-in BaseVisionModel implementation.
    Fully local — no network calls after the initial model download.
    """

    name = "qwen_vl"

    def __init__(
        self,
        model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct",
    ) -> None:
        self._model_id = model_id

    @classmethod
    def from_settings(cls) -> "QwenVLModel":
        return cls()

    def analyze_frame(self, frame: Frame) -> FrameAnalysis:
        tracer = get_tracer()
        with tracer.start_as_current_span("vision.qwen_vl") as span:
            span.set_attribute("vision.model", self.name)
            span.set_attribute("vision.timestamp_ms", frame.timestamp_ms)

            t0 = time.monotonic()
            model, processor, process_vision_info, device = _load_model(self._model_id)

            import torch
            import json as _json

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "image": Path(frame.path).as_uri(),
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ]

            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            ).to(device)

            with torch.no_grad():
                generated_ids = model.generate(**inputs, max_new_tokens=256)

            trimmed = [
                out_ids[len(in_ids):]
                for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            raw = processor.batch_decode(
                trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0].strip()

            latency_ms = int((time.monotonic() - t0) * 1000)

            try:
                if raw.startswith("```"):
                    parts = raw.split("```")
                    raw = parts[1] if len(parts) > 1 else raw
                    raw = raw[4:].strip() if raw.startswith("json") else raw.strip()
                data = _json.loads(raw)
            except Exception:
                data = {}

            return FrameAnalysis(
                frame_type=data.get("frame_type", "other"),
                ocr_text=data.get("ocr_text", ""),
                objects=data.get("objects", []),
                confidence=float(data.get("confidence", 0.0)),
                model_name=self.name,
                latency_ms=latency_ms,
            )
