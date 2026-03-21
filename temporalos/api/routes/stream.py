"""WebSocket streaming endpoint for real-time video analysis.

Protocol (text + binary frames):
  Client → binary  : raw audio bytes (16kHz 16-bit mono PCM recommended)
  Client → JSON    : {"type": "end"}            — signals end of audio stream
  Server → JSON    : {"type": "result", ...}    — partial extraction
  Server → JSON    : {"type": "done", ...}      — processing complete
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...audio.streaming import get_streaming_asr
from ...pipeline.streaming_pipeline import StreamingPipeline

router = APIRouter(tags=["streaming"])


@router.websocket("/ws/stream")
async def stream_process(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time speech → structured intelligence.

    Auto-detects the best ASR backend:
    - Deepgram (if DEEPGRAM_API_KEY is set)
    - Mock (deterministic fallback for dev/test)
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)
    asr = get_streaming_asr()  # Auto-detects real vs mock
    pipeline = StreamingPipeline(asr=asr)

    async def _push_results() -> None:
        async for result in pipeline.process(audio_queue):
            payload: dict[str, Any] = {
                "type": "result",
                "session_id": session_id,
                "timestamp_ms": result.timestamp_ms,
                "transcript": result.transcript,
                "is_final": result.is_final,
            }
            if result.extraction:
                payload["extraction"] = result.extraction.to_dict()
            try:
                await websocket.send_text(json.dumps(payload))
            except Exception:
                return  # client disconnected mid-stream
        try:
            await websocket.send_text(json.dumps({"type": "done", "session_id": session_id}))
        except Exception:
            pass

    result_task = asyncio.create_task(_push_results())

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive(), timeout=30.0)
            except asyncio.TimeoutError:
                break

            if msg["type"] == "websocket.disconnect":
                break
            elif msg["type"] == "websocket.receive":
                if msg.get("bytes"):
                    try:
                        audio_queue.put_nowait(msg["bytes"])
                    except asyncio.QueueFull:
                        pass  # drop frame under back-pressure
                elif msg.get("text"):
                    data = json.loads(msg["text"])
                    if data.get("type") == "end":
                        await audio_queue.put(None)
                        break
    except WebSocketDisconnect:
        pass
    finally:
        # Ensure the producer unblocks
        try:
            audio_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        try:
            await asyncio.wait_for(result_task, timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            result_task.cancel()
