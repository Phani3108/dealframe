"""WebSocket endpoint for the Live Negotiation Copilot.

Protocol:
  Client → binary  : raw PCM 16 kHz / 16-bit / mono audio chunks
  Client → JSON    : {"type": "end"}             — signal end of audio stream
  Server → JSON    : {"type": "transcript", text, ts_ms, is_final}
  Server → JSON    : {"type": "extraction", ts_ms, extraction}
  Server → JSON    : {"type": "cue", ts_ms, cue: {type,title,message,priority}}
  Server → JSON    : {"type": "done"}

This endpoint chains the existing StreamingPipeline with the LiveCopilot
prompt generator so that cue cards are produced in real time from the same
ASR+extraction stream. No new infra required.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...audio.streaming import get_streaming_asr
from ...pipeline.streaming_pipeline import StreamingPipeline

router = APIRouter(tags=["live-copilot"])


async def _safe_send(ws: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await ws.send_text(json.dumps(payload))
        return True
    except Exception:
        return False


@router.websocket("/ws/live-copilot")
async def live_copilot_stream(websocket: WebSocket) -> None:
    """Bidirectional live-copilot WebSocket.

    Accepts PCM audio frames, streams transcript + extraction + cue events.
    Falls back gracefully to mock ASR when Deepgram is not configured.
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=200)

    # Lazy imports keep the web process lightweight when Live Copilot is not used.
    copilot_cls: Any
    try:
        from ...intelligence.copilot import LiveCopilot as _LiveCopilot
        copilot_cls = _LiveCopilot
    except Exception:  # pragma: no cover — defensive
        copilot_cls = None

    asr = get_streaming_asr()
    pipeline = StreamingPipeline(asr=asr)
    copilot = copilot_cls() if copilot_cls is not None else None

    await _safe_send(websocket, {"type": "ready", "session_id": session_id})

    async def _push_results() -> None:
        async for result in pipeline.process(audio_queue):
            ts_ms = result.timestamp_ms
            ok = await _safe_send(
                websocket,
                {
                    "type": "transcript",
                    "session_id": session_id,
                    "ts_ms": ts_ms,
                    "text": result.transcript,
                    "is_final": result.is_final,
                },
            )
            if not ok:
                return

            extraction_dict: dict[str, Any] | None = None
            if result.extraction is not None:
                extraction_dict = result.extraction.to_dict()
                await _safe_send(
                    websocket,
                    {
                        "type": "extraction",
                        "session_id": session_id,
                        "ts_ms": ts_ms,
                        "extraction": extraction_dict,
                    },
                )

            # Synthesize cue cards (pure python — no external calls)
            if copilot is not None:
                segment = {
                    "transcript": result.transcript,
                    "extraction": extraction_dict or {},
                    "timestamp_ms": ts_ms,
                }
                try:
                    cues = copilot.process_segment(segment)
                except Exception:
                    cues = []
                for cue in cues:
                    cue_payload = cue.to_dict() if hasattr(cue, "to_dict") else cue
                    await _safe_send(
                        websocket,
                        {
                            "type": "cue",
                            "session_id": session_id,
                            "ts_ms": ts_ms,
                            "cue": cue_payload,
                        },
                    )

        await _safe_send(websocket, {"type": "done", "session_id": session_id})

    result_task = asyncio.create_task(_push_results())

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive(), timeout=60.0)
            except asyncio.TimeoutError:
                break

            mtype = msg.get("type")
            if mtype == "websocket.disconnect":
                break
            if mtype != "websocket.receive":
                continue

            raw = msg.get("bytes")
            if raw:
                try:
                    audio_queue.put_nowait(raw)
                except asyncio.QueueFull:
                    # drop under back-pressure to keep stream live
                    pass
                continue

            text = msg.get("text")
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "end":
                await audio_queue.put(None)
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            audio_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        try:
            await asyncio.wait_for(result_task, timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            result_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
