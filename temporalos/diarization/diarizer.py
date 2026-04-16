"""Speaker diarization — assigns SPEAKER_A / SPEAKER_B labels to word sequences.

Uses pause-boundary heuristic for zero-dependency operation.
Lazy-imports pyannote.audio when available for production-grade diarization.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from temporalos.core.types import Word

logger = logging.getLogger(__name__)


@dataclass
class DiarizationSegment:
    speaker: str
    start_ms: int
    end_ms: int

    def to_dict(self) -> dict:
        s = self.start_ms
        return {
            "speaker": self.speaker,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "start_str": f"{s // 60000:02d}:{(s // 1000) % 60:02d}",
            "duration_s": round((self.end_ms - self.start_ms) / 1000, 1),
        }


class MockDiarizer:
    """
    Pause-boundary speaker diarizer.

    Detects speaker turns via silence gaps ≥ pause_threshold_ms between words.
    Alternates SPEAKER_A / SPEAKER_B at each detected boundary.
    Suitable for demos and testing; swap with pyannote for production.
    """

    SPEAKERS = ["SPEAKER_A", "SPEAKER_B"]

    def __init__(self, pause_threshold_ms: int = 1500):
        self.pause_threshold_ms = pause_threshold_ms

    def diarize(self, words: List[Word]) -> List[Word]:
        """Assign speaker labels — returns new Word objects with speaker set."""
        if not words:
            return []

        result: List[Word] = []
        idx = 0

        for i, w in enumerate(words):
            if i > 0:
                gap = w.start_ms - words[i - 1].end_ms
                if gap >= self.pause_threshold_ms:
                    idx = (idx + 1) % 2
            result.append(
                Word(text=w.text, start_ms=w.start_ms, end_ms=w.end_ms,
                     speaker=self.SPEAKERS[idx])
            )
        return result

    def get_segments(self, words: List[Word]) -> List[DiarizationSegment]:
        """Collapse labeled words into contiguous speaker segments."""
        labeled = self.diarize(words)
        if not labeled:
            return []

        segs: List[DiarizationSegment] = []
        cur_speaker = labeled[0].speaker
        cur_start = labeled[0].start_ms
        cur_end = labeled[0].end_ms

        for w in labeled[1:]:
            if w.speaker != cur_speaker:
                segs.append(DiarizationSegment(cur_speaker, cur_start, cur_end))
                cur_speaker = w.speaker
                cur_start = w.start_ms
            cur_end = w.end_ms

        segs.append(DiarizationSegment(cur_speaker, cur_start, cur_end))
        return segs


class PyAnnoteDiarizer:
    """Production-grade speaker diarization using pyannote-audio.

    Requires: pip install pyannote-audio torch
    And a Hugging Face token with access to pyannote/speaker-diarization-3.1.
    """

    def __init__(self, hf_token: Optional[str] = None, num_speakers: Optional[int] = None):
        self._hf_token = hf_token
        self._num_speakers = num_speakers
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            from pyannote.audio import Pipeline
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self._hf_token,
            )
        return self._pipeline

    def diarize_audio(self, audio_path: str) -> List[DiarizationSegment]:
        """Run pyannote diarization on an audio file."""
        pipeline = self._get_pipeline()
        kwargs = {}
        if self._num_speakers:
            kwargs["num_speakers"] = self._num_speakers
        diarization = pipeline(audio_path, **kwargs)

        segments: List[DiarizationSegment] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(DiarizationSegment(
                speaker=speaker,
                start_ms=int(turn.start * 1000),
                end_ms=int(turn.end * 1000),
            ))
        return segments

    def apply_to_words(self, words: List[Word], audio_path: str) -> List[Word]:
        """Assign speaker labels to words based on pyannote segments."""
        segments = self.diarize_audio(audio_path)
        if not segments:
            return words

        # Map speaker IDs to consistent labels
        speaker_map: Dict[str, str] = {}
        idx = 0
        for seg in segments:
            if seg.speaker not in speaker_map:
                speaker_map[seg.speaker] = f"SPEAKER_{chr(65 + idx)}"
                idx = min(idx + 1, 25)  # cap at 26 speakers

        result: List[Word] = []
        for w in words:
            mid = (w.start_ms + w.end_ms) // 2
            speaker = "SPEAKER_A"  # default
            for seg in segments:
                if seg.start_ms <= mid <= seg.end_ms:
                    speaker = speaker_map.get(seg.speaker, seg.speaker)
                    break
            result.append(Word(
                text=w.text, start_ms=w.start_ms, end_ms=w.end_ms,
                speaker=speaker,
            ))
        return result

    def get_segments(self, words: List[Word]) -> List[DiarizationSegment]:
        """Get speaker segments from already-labeled words."""
        if not words:
            return []
        segs: List[DiarizationSegment] = []
        cur_speaker = words[0].speaker or "SPEAKER_A"
        cur_start = words[0].start_ms
        cur_end = words[0].end_ms

        for w in words[1:]:
            speaker = w.speaker or cur_speaker
            if speaker != cur_speaker:
                segs.append(DiarizationSegment(cur_speaker, cur_start, cur_end))
                cur_speaker = speaker
                cur_start = w.start_ms
            cur_end = w.end_ms

        segs.append(DiarizationSegment(cur_speaker, cur_start, cur_end))
        return segs

    def diarize(self, words: List[Word]) -> List[Word]:
        """Uniform ``Diarizer`` interface — falls back to heuristic when no audio is available.

        ``PyAnnoteDiarizer`` needs an audio path to run real diarization via
        :meth:`apply_to_words`. When callers only pass ``words`` (no audio), we
        transparently reuse the heuristic so the factory's return type stays a
        consistent duck-typed ``diarize(words) -> List[Word]`` contract.
        """
        return MockDiarizer().diarize(words)


def get_diarizer(
    pause_threshold_ms: int = 1500,
    use_pyannote: Optional[bool] = None,
    hf_token: Optional[str] = None,
    num_speakers: Optional[int] = None,
) -> MockDiarizer | PyAnnoteDiarizer:
    """Factory — prefers PyAnnoteDiarizer when available, falls back to heuristic.

    ``use_pyannote`` tri-state:
      * ``True``  — require pyannote; fall back if unavailable and log a warning.
      * ``False`` — always use the heuristic diarizer.
      * ``None``  — auto-detect. Enabled when ``DEALFRAME_DIARIZER != "mock"``
        and either pyannote is importable or a HUGGINGFACE_TOKEN is present.
    """
    import os

    if use_pyannote is False:
        return MockDiarizer(pause_threshold_ms=pause_threshold_ms)

    env_pref = (os.environ.get("DEALFRAME_DIARIZER") or "").lower()
    if env_pref == "mock":
        return MockDiarizer(pause_threshold_ms=pause_threshold_ms)

    resolved_token = hf_token or os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")

    if use_pyannote or env_pref == "pyannote":
        want_pyannote = True
    else:  # auto
        want_pyannote = True  # opt-in by default when importable

    if want_pyannote:
        try:
            from pyannote.audio import Pipeline  # noqa: F401
            return PyAnnoteDiarizer(hf_token=resolved_token, num_speakers=num_speakers)
        except ImportError:
            if use_pyannote:
                logger.warning(
                    "pyannote-audio requested but not installed — falling back to heuristic diarizer",
                )
            else:
                logger.debug("pyannote-audio not installed — using heuristic diarizer")
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Could not initialise pyannote diarizer: %s", exc)

    return MockDiarizer(pause_threshold_ms=pause_threshold_ms)
