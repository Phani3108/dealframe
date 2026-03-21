"""Smart Clip Reels — auto-generate highlight compilations from calls.

Curates segments by criteria:
- Best objection handles (high risk followed by resolution)
- Competitor mentions with battlecard responses
- Decision moments (strong buying signals)
- Key topic segments (pricing, timeline, authority)

Produces clip reel metadata for video assembly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Clip:
    """A single clip within a reel."""
    id: str
    job_id: str
    segment_index: int
    start_ms: int
    end_ms: int
    category: str  # objection_handle | competitor_mention | decision_moment | key_topic | highlight
    title: str
    score: float  # relevance/importance score 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "segment_index": self.segment_index,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "category": self.category,
            "title": self.title,
            "score": round(self.score, 3),
            "metadata": self.metadata,
        }


@dataclass
class ClipReel:
    """A curated collection of clips."""
    id: str
    name: str
    clips: List[Clip] = field(default_factory=list)
    total_duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "clip_count": len(self.clips),
            "total_duration_ms": self.total_duration_ms,
            "clips": [c.to_dict() for c in self.clips],
        }


def _score_objection_handle(seg: Dict[str, Any], idx: int,
                            segments: List[Dict[str, Any]]) -> float:
    """Score how well an objection was handled based on following segment risk."""
    ext = seg.get("extraction", seg)
    objections = ext.get("objections", [])
    if not objections:
        return 0.0
    risk = ext.get("risk_score", 0.5)
    # Check if next segment has lower risk (good handle)
    next_risk = 0.5
    if idx + 1 < len(segments):
        next_ext = segments[idx + 1].get("extraction", segments[idx + 1])
        next_risk = next_ext.get("risk_score", 0.5)
    resolution = max(risk - next_risk, 0)
    return min(0.5 + resolution, 1.0)


def _score_decision_moment(seg: Dict[str, Any]) -> float:
    ext = seg.get("extraction", seg)
    signals = ext.get("decision_signals", [])
    if not signals:
        return 0.0
    return min(0.6 + 0.1 * len(signals), 1.0)


def generate_clips(job_id: str, segments: List[Dict[str, Any]],
                   categories: Optional[List[str]] = None,
                   max_clips: int = 20) -> List[Clip]:
    """Generate clips from segments based on specified categories."""
    if categories is None:
        categories = ["objection_handle", "competitor_mention", "decision_moment", "key_topic"]

    clips: List[Clip] = []

    for idx, seg in enumerate(segments):
        ext = seg.get("extraction", seg)
        ts = seg.get("timestamp_ms", idx * 30000)
        duration = seg.get("duration_ms", 30000)
        transcript = seg.get("transcript", "")

        # Objection handles
        if "objection_handle" in categories:
            score = _score_objection_handle(seg, idx, segments)
            if score > 0.4:
                objections = ext.get("objections", [])
                clips.append(Clip(
                    id=uuid.uuid4().hex[:10],
                    job_id=job_id,
                    segment_index=idx,
                    start_ms=ts,
                    end_ms=ts + duration,
                    category="objection_handle",
                    title=f"Objection: {objections[0][:50]}" if objections else "Objection Handle",
                    score=score,
                    metadata={"objections": objections},
                ))

        # Competitor mentions
        if "competitor_mention" in categories:
            lower = transcript.lower() if isinstance(transcript, str) else ""
            competitors = [c for c in ["gong", "chorus", "clari", "salesforce", "hubspot"]
                           if c in lower]
            if competitors:
                clips.append(Clip(
                    id=uuid.uuid4().hex[:10],
                    job_id=job_id,
                    segment_index=idx,
                    start_ms=ts,
                    end_ms=ts + duration,
                    category="competitor_mention",
                    title=f"Competitor: {', '.join(competitors)}",
                    score=0.7,
                    metadata={"competitors": competitors},
                ))

        # Decision moments
        if "decision_moment" in categories:
            score = _score_decision_moment(seg)
            if score > 0.5:
                signals = ext.get("decision_signals", [])
                clips.append(Clip(
                    id=uuid.uuid4().hex[:10],
                    job_id=job_id,
                    segment_index=idx,
                    start_ms=ts,
                    end_ms=ts + duration,
                    category="decision_moment",
                    title=f"Signal: {signals[0][:50]}" if signals else "Decision Moment",
                    score=score,
                    metadata={"signals": signals},
                ))

        # Key topics
        if "key_topic" in categories:
            topic = ext.get("topic", "").lower()
            important_topics = ["pricing", "timeline", "budget", "authority", "decision", "contract"]
            if any(t in topic for t in important_topics):
                clips.append(Clip(
                    id=uuid.uuid4().hex[:10],
                    job_id=job_id,
                    segment_index=idx,
                    start_ms=ts,
                    end_ms=ts + duration,
                    category="key_topic",
                    title=f"Topic: {ext.get('topic', 'Unknown')[:50]}",
                    score=0.6,
                    metadata={"topic": ext.get("topic", "")},
                ))

    # Sort by score, limit
    clips.sort(key=lambda c: c.score, reverse=True)
    return clips[:max_clips]


def build_reel(name: str, job_id: str, segments: List[Dict[str, Any]],
               categories: Optional[List[str]] = None,
               max_clips: int = 20,
               video_path: Optional[str] = None) -> ClipReel:
    """Build a complete clip reel.

    If *video_path* is provided and FFmpeg is available, actual video clips
    are extracted to disk.  Otherwise only metadata is produced.
    """
    clips = generate_clips(job_id, segments, categories, max_clips)
    # Sort clips by time for reel playback order
    clips.sort(key=lambda c: c.start_ms)
    total_ms = sum(c.end_ms - c.start_ms for c in clips)

    # Attempt real FFmpeg extraction when a video file is available
    if video_path:
        try:
            from ..clips.extractor import ClipSpec, get_clip_extractor
            import os
            if os.path.exists(video_path):
                extractor = get_clip_extractor()
                for clip in clips:
                    try:
                        spec = ClipSpec(
                            label=clip.title[:20],
                            start_ms=clip.start_ms,
                            end_ms=clip.end_ms,
                            risk_score=clip.score,
                            topic=clip.metadata.get("topic", ""),
                        )
                        result = extractor.extract(video_path, job_id, spec)
                        clip.metadata["clip_path"] = str(result.path)
                        clip.metadata["clip_size_bytes"] = result.size_bytes
                    except Exception:
                        pass  # FFmpeg not installed or failed — metadata only
        except Exception:
            pass

    return ClipReel(
        id=uuid.uuid4().hex[:10],
        name=name,
        clips=clips,
        total_duration_ms=total_ms,
    )
