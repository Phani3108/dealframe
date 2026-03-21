"""Streaming ASR interface with a deterministic MockStreamingASR fallback.

Protocol:
  - Caller pushes raw audio bytes into an asyncio.Queue (None = end-of-stream)
  - Implementation returns a second Queue[TranscriptChunk | None]
  - Consumers drain the result queue until they receive None (sentinel)

Backends:
  - MockStreamingASR  — deterministic, no external APIs, used in tests and local mode
  - (optional) DeepgramStreamingASR — lazy-imported when backend="deepgram"
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TranscriptChunk:
    """A partial or final transcript result from streaming ASR."""

    text: str
    start_ms: int
    end_ms: int
    is_final: bool = False
    confidence: float = 0.0
    words: list[dict] = field(default_factory=list)  # [{word, start_ms, end_ms}]


class StreamingASRBase(ABC):
    @abstractmethod
    async def stream(self, audio_chunks: asyncio.Queue) -> asyncio.Queue:
        """Given a queue of raw audio bytes, return a queue of TranscriptChunks."""
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class MockStreamingASR(StreamingASRBase):
    """
    Deterministic mock that converts accumulated audio bytes into timed TranscriptChunks.
    Uses only asyncio — no external API calls, no ML models.

    Byte-rate assumption: 16kHz 16-bit mono PCM = 32,000 bytes/second.
    """

    def __init__(self, words_per_second: float = 2.5) -> None:
        self._wps = words_per_second
        self._closed = False

    async def stream(self, audio_chunks: asyncio.Queue) -> asyncio.Queue:
        results: asyncio.Queue[TranscriptChunk | None] = asyncio.Queue()

        async def _produce() -> None:
            accumulated: list[bytes] = []
            while True:
                chunk = await audio_chunks.get()
                if chunk is None:
                    break
                accumulated.append(chunk)

            total_bytes = sum(len(c) for c in accumulated)
            # 32000 bytes ≈ 1 second of 16kHz 16-bit mono audio
            duration_ms = max(1000, int(total_bytes / 32))
            n_words = max(1, int((duration_ms / 1000) * self._wps))
            ms_per_word = max(1, duration_ms // n_words)

            for i in range(0, n_words, 5):
                batch_size = min(5, n_words - i)
                batch_words = [f"word{i + j}" for j in range(batch_size)]
                start_ms = i * ms_per_word
                end_ms = min((i + batch_size) * ms_per_word, duration_ms)
                words_meta = [
                    {
                        "word": w,
                        "start_ms": start_ms + j * ms_per_word,
                        "end_ms": start_ms + (j + 1) * ms_per_word,
                    }
                    for j, w in enumerate(batch_words)
                ]
                await results.put(
                    TranscriptChunk(
                        text=" ".join(batch_words),
                        start_ms=start_ms,
                        end_ms=end_ms,
                        is_final=(i + batch_size >= n_words),
                        confidence=0.92,
                        words=words_meta,
                    )
                )
                await asyncio.sleep(0)  # yield control

            await results.put(None)  # sentinel

        asyncio.create_task(_produce())
        return results

    async def close(self) -> None:
        self._closed = True


def get_streaming_asr(backend: str = "auto") -> StreamingASRBase:
    """Factory: returns the appropriate StreamingASR implementation.

    With backend='auto' (default), tries Deepgram first if DEEPGRAM_API_KEY
    is set, then falls back to MockStreamingASR.
    """
    if backend in ("deepgram", "auto"):
        try:
            import os
            if backend == "deepgram" or os.environ.get("DEEPGRAM_API_KEY"):
                from .deepgram import DeepgramStreamingASR
                return DeepgramStreamingASR()
        except (ImportError, ValueError, Exception):
            if backend == "deepgram":
                # Requested Deepgram but unavailable — fall back to mock
                return MockStreamingASR()
    if backend not in ("auto", "mock"):
        # Unknown backend — fall back to mock rather than crash
        return MockStreamingASR()
    return MockStreamingASR()
