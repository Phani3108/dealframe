"""Video Q&A Agent — answers natural-language questions over the video library.

Architecture:
  1. Each processed job is indexed: each segment → one Document in TFIDFStore.
  2. At query time: retrieve top-K docs, build a context window, generate answer.
     In mock mode: context is returned as-is (no LLM call).
     In production: pass context to GPT-4o / Claude for synthesis.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from temporalos.agents.vector_store import Document, TFIDFStore

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    job_id: str
    segment_index: int
    timestamp: str
    topic: str
    risk_score: float
    excerpt: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "segment_index": self.segment_index,
            "timestamp": self.timestamp,
            "topic": self.topic,
            "risk_score": self.risk_score,
            "excerpt": self.excerpt[:200],
        }


@dataclass
class QAAnswer:
    question: str
    answer: str
    citations: List[Citation] = field(default_factory=list)
    model: str = "mock"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "model": self.model,
        }


class VideoQAAgent:
    """Answers questions about the indexed video library.

    Usage:
        agent = VideoQAAgent()
        agent.index_job(job_id, intel_dict)
        answer = agent.ask("What objections came up in the Acme call?")
    """

    def __init__(self, top_k: int = 5) -> None:
        self._store = TFIDFStore()
        self.top_k = top_k

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_job(self, job_id: str, intel: Dict[str, Any]) -> int:
        """Index all segments from a processed job. Returns doc count added."""
        segments = intel.get("segments", [])
        count = 0
        for i, seg in enumerate(segments):
            ext = seg.get("extraction", seg)
            ts = seg.get("timestamp_str", f"seg-{i}")
            text_parts = [
                f"job={job_id}",
                f"topic={ext.get('topic', 'general')}",
                f"risk={ext.get('risk', 'low')}",
                f"objections: {' '.join(ext.get('objections', []))}",
                f"signals: {' '.join(ext.get('decision_signals', []))}",
                f"transcript: {seg.get('transcript', '')}",
            ]
            doc = Document(
                id=f"{job_id}_seg{i}",
                text=" ".join(text_parts),
                metadata={
                    "job_id": job_id,
                    "segment_index": i,
                    "timestamp": ts,
                    "risk_score": ext.get("risk_score", 0.0),
                    "topic": ext.get("topic", "general"),
                    "objections": ext.get("objections", []),
                    "decision_signals": ext.get("decision_signals", []),
                    "transcript_excerpt": seg.get("transcript", "")[:300],
                },
            )
            self._store.add(doc)
            count += 1
        logger.debug("Indexed %d segments from job %s", count, job_id)
        return count

    def remove_job(self, job_id: str) -> None:
        for doc_id in [k for k in self._store._docs if k.startswith(f"{job_id}_")]:
            self._store.remove(doc_id)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def ask(self, question: str,
            filter_job_id: Optional[str] = None) -> QAAnswer:
        """Answer a natural language question over indexed videos.

        Tries LLM synthesis first; falls back to rule-based if no LLM configured.
        """
        filter_meta = {"job_id": filter_job_id} if filter_job_id else None
        hits = self._store.search(question, top_k=self.top_k, filter_meta=filter_meta)

        if not hits:
            return QAAnswer(
                question=question,
                answer="No relevant video content found for your question. "
                       "Make sure jobs are indexed before querying.",
                citations=[],
            )

        # Build context from top hits
        context_blocks = []
        citations: List[Citation] = []
        for doc, score in hits:
            m = doc.metadata
            context_blocks.append(
                f"[{m['job_id']} @ {m['timestamp']} | risk={round(m['risk_score']*100)}%]\n"
                f"Topic: {m['topic']}\n"
                f"Objections: {'; '.join(m.get('objections', [])) or 'none'}\n"
                f"Signals: {'; '.join(m.get('decision_signals', [])) or 'none'}\n"
                f"Excerpt: {m.get('transcript_excerpt', '')[:200]}"
            )
            citations.append(Citation(
                job_id=m["job_id"],
                segment_index=m["segment_index"],
                timestamp=m["timestamp"],
                topic=m["topic"],
                risk_score=m["risk_score"],
                excerpt=m.get("transcript_excerpt", ""),
            ))

        # Try LLM synthesis, fall back to rule-based
        answer, model = self._synthesize(question, hits, context_blocks)

        return QAAnswer(question=question, answer=answer, citations=citations, model=model)

    def _synthesize(self, question: str, hits: list,
                    context_blocks: List[str]) -> tuple:
        """Try LLM synthesis; fall back to mock."""
        try:
            import asyncio
            from temporalos.llm.router import get_llm, MockLLMProvider
            llm = get_llm()
            if not isinstance(llm, MockLLMProvider):
                context = "\n\n".join(context_blocks)
                prompt = (
                    f"Based on the following video call data, answer this question:\n\n"
                    f"Question: {question}\n\n"
                    f"Relevant segments:\n{context}\n\n"
                    f"Provide a concise, specific answer with references to the data."
                )
                system = "You are a video intelligence analyst. Answer questions based on the call data provided."
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We're in a sync context called from async — use thread
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            resp = pool.submit(
                                lambda: asyncio.run(llm.complete(prompt, system=system))
                            ).result(timeout=30)
                    else:
                        resp = loop.run_until_complete(llm.complete(prompt, system=system))
                    return resp.text, resp.model
                except Exception as exc:
                    logger.warning("LLM synthesis failed, using rule-based: %s", exc)
        except Exception:
            pass
        return self._synthesize_mock(question, hits), "rule-based"

    def _synthesize_mock(self, question: str,
                         hits: list) -> str:
        """Rule-based answer synthesis without LLM — for offline/test use."""
        q_lower = question.lower()
        all_obj: List[str] = []
        all_signals: List[str] = []
        topics = []
        risk_scores = []

        for doc, _ in hits:
            m = doc.metadata
            all_obj.extend(m.get("objections", []))
            all_signals.extend(m.get("decision_signals", []))
            topics.append(m.get("topic", "general"))
            risk_scores.append(m.get("risk_score", 0))

        unique_obj = list(dict.fromkeys(all_obj))[:5]
        unique_sig = list(dict.fromkeys(all_signals))[:5]
        avg_risk = sum(risk_scores) / max(len(risk_scores), 1)

        if any(kw in q_lower for kw in ("objection", "concern", "pushback", "hesitation")):
            if unique_obj:
                return f"Found {len(unique_obj)} objection(s): {'; '.join(unique_obj)}."
            return "No objections detected in the relevant segments."

        if any(kw in q_lower for kw in ("decision", "signal", "next step", "commitment")):
            if unique_sig:
                return f"Decision signals: {'; '.join(unique_sig)}."
            return "No decision signals found in the relevant segments."

        if any(kw in q_lower for kw in ("risk", "danger", "problem", "issue")):
            return (
                f"Average risk across {len(hits)} relevant segments: "
                f"{round(avg_risk * 100)}%. "
                + ("Key concerns: " + "; ".join(unique_obj[:3]) if unique_obj else "")
            )

        # Generic summary
        return (
            f"Found {len(hits)} relevant moment(s) covering topics: "
            f"{', '.join(list(dict.fromkeys(topics))[:3])}. "
            f"Risk level: {round(avg_risk * 100)}%. "
            + (f"Objections: {'; '.join(unique_obj[:3])}." if unique_obj else "")
        )

    @property
    def index_size(self) -> int:
        return len(self._store)


# Singleton
_agent: Optional[VideoQAAgent] = None


def get_qa_agent() -> VideoQAAgent:
    global _agent
    if _agent is None:
        _agent = VideoQAAgent()
    return _agent
