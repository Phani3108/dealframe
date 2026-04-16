"""DealFrame Python SDK — programmatic access to the Negotiation Intelligence API.

Quick start:
    from temporalos_sdk import DealFrameClient

    client = DealFrameClient("http://localhost:8000")
    job = client.upload("meeting.mp4")
    result = client.wait_for_result(job.job_id)
    print(result.segments[0]["topic"])

The legacy ``TemporalOSClient`` / ``TemporalOSError`` names remain exported
as aliases for back-compat with existing integrations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json


@dataclass
class JobResult:
    """Result of a processed video analysis job."""
    job_id: str
    status: str
    segments: List[Dict[str, Any]] = field(default_factory=list)
    transcript: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnnotationResult:
    """A single annotation."""
    id: str
    job_id: str
    label: str
    comment: str = ""
    segment_index: int = 0
    resolved: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


class TemporalOSError(Exception):
    """SDK error with HTTP status code."""
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class TemporalOSClient:
    """Python SDK client for the TemporalOS API.

    Args:
        base_url: Base URL of the TemporalOS API (e.g. 'http://localhost:8000')
        api_key: Optional API key for authentication
        timeout: HTTP request timeout in seconds
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Accept": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _request(self, method: str, path: str, data: Optional[bytes] = None,
                 content_type: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self._base}{path}"
        headers = self._headers()
        if content_type:
            headers["Content-Type"] = content_type
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode()
            raise TemporalOSError(f"HTTP {e.code}: {body}", status_code=e.code) from e

    def _get(self, path: str) -> Dict[str, Any]:
        return self._request("GET", path)

    def _post(self, path: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        data = json.dumps(payload or {}).encode() if payload else None
        return self._request("POST", path, data, "application/json")

    # ── Core ─────────────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """Check API health."""
        return self._get("/health")

    def upload(self, video_path: str) -> JobResult:
        """Upload a video file for processing.

        Args:
            video_path: Path to the video file

        Returns:
            JobResult with job_id and initial status
        """
        p = Path(video_path)
        if not p.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        boundary = "----TemporalOSBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{p.name}"\r\n'
            f"Content-Type: video/mp4\r\n\r\n"
        ).encode() + p.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

        result = self._request(
            "POST", "/api/v1/process", body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        return JobResult(
            job_id=result.get("job_id", ""),
            status=result.get("status", "pending"),
            raw=result,
        )

    def get_job(self, job_id: str) -> JobResult:
        """Get the status and result of a job."""
        result = self._get(f"/api/v1/process/{job_id}")
        segments = result.get("result", {}).get("segments", [])
        transcript = result.get("result", {}).get("transcript", "")
        return JobResult(
            job_id=job_id,
            status=result.get("status", "unknown"),
            segments=segments,
            transcript=transcript,
            raw=result,
        )

    def wait_for_result(self, job_id: str, poll_interval: float = 2.0,
                        max_wait: float = 300.0) -> JobResult:
        """Poll until job completes or times out."""
        start = time.time()
        while time.time() - start < max_wait:
            job = self.get_job(job_id)
            if job.status in ("completed", "failed"):
                return job
            time.sleep(poll_interval)
        raise TemporalOSError(f"Job {job_id} did not complete within {max_wait}s")

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs."""
        result = self._get("/api/v1/process")
        jobs = result.get("jobs", {})
        if isinstance(jobs, dict):
            return [{"id": k, **v} for k, v in jobs.items()]
        return jobs

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Semantic search across all processed videos."""
        result = self._post("/api/v1/search", {"query": query, "top_k": top_k})
        return result.get("results", [])

    # ── Intelligence ─────────────────────────────────────────────────────────

    def get_objections(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get top objections across all jobs."""
        result = self._get(f"/api/v1/intelligence/objections?top_n={top_n}")
        return result.get("objections", [])

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get risk distribution summary."""
        return self._get("/api/v1/intelligence/risk-summary")

    # ── Annotations ──────────────────────────────────────────────────────────

    def list_annotations(self, job_id: str) -> List[AnnotationResult]:
        """List annotations for a job."""
        result = self._get(f"/api/v1/annotations?job_id={job_id}")
        return [
            AnnotationResult(
                id=a["id"], job_id=a["job_id"], label=a["label"],
                comment=a.get("comment", ""), segment_index=a.get("segment_index", 0),
                resolved=a.get("resolved", False), raw=a,
            )
            for a in result.get("annotations", [])
        ]

    def create_annotation(self, job_id: str, segment_index: int,
                          start_word: int, end_word: int, label: str,
                          comment: str = "") -> AnnotationResult:
        """Create a new annotation."""
        result = self._post("/api/v1/annotations", {
            "job_id": job_id, "segment_index": segment_index,
            "start_word": start_word, "end_word": end_word,
            "label": label, "comment": comment,
        })
        a = result["annotation"]
        return AnnotationResult(
            id=a["id"], job_id=a["job_id"], label=a["label"],
            comment=a.get("comment", ""), raw=a,
        )

    # ── Patterns ─────────────────────────────────────────────────────────────

    def get_patterns(self, pattern_type: str = "objection_risk") -> Dict[str, Any]:
        """Get mined patterns."""
        return self._get(f"/api/v1/patterns?pattern_type={pattern_type}")

    # ── Copilot ──────────────────────────────────────────────────────────────

    def analyze_live(self, transcript: str) -> Dict[str, Any]:
        """Get coaching signals from a live transcript."""
        return self._post("/api/v1/copilot/analyze", {"transcript_so_far": transcript})

    # ── Admin ────────────────────────────────────────────────────────────────

    def system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics."""
        return self._get("/api/v1/admin/stats")


# ── Rebranded aliases ────────────────────────────────────────────────────────
# New code should prefer these DealFrame-branded names. Legacy names above
# remain for wire-level back-compat with existing integrations / docs.

DealFrameClient = TemporalOSClient
DealFrameError = TemporalOSError

__all__ = [
    "TemporalOSClient",
    "TemporalOSError",
    "DealFrameClient",
    "DealFrameError",
    "JobResult",
    "AnnotationResult",
]
