"""Chat-with-Deal — per-video conversational intelligence with SSE streaming
and timestamp citations that deep-link back into the video player.

The route supports both a simple JSON mutation (for non-streaming clients) and
an SSE streaming endpoint that emits incremental tokens and citation metadata.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


_SYSTEM_PROMPT = """\
You are DealFrame's conversational deal analyst. You are given the segment
timeline of a recorded sales / procurement / negotiation call, along with
extracted objections, risks, and decision signals. Answer the user's
question grounded ONLY in the provided segments.

Rules:
- Always cite the timestamps (mm:ss) of the segments that support your answer.
- When citing, use the marker [ts=MM:SS] inline, immediately after the claim.
- If the transcript does not contain the answer, say so honestly.
- Be concise, structured, and actionable.
"""


def _get_jobs() -> dict:
    from .process import _jobs
    return _jobs


def _build_segment_context(job: dict, max_segments: int = 40) -> tuple[str, list[dict]]:
    """Compact view of the deal's segments for the LLM context window.

    Returns (prompt_chunk, citation_catalog) — the catalog lets us resolve
    timestamp strings back to segment indices for UI deep-links.
    """
    intel = job.get("result") or job.get("intelligence") or {}
    segments: list[dict] = intel.get("segments") or []

    # Prefer high-signal segments first to stay within context.
    scored = []
    for i, pair in enumerate(segments):
        ext = pair.get("extraction", {}) if isinstance(pair, dict) and "extraction" in pair else pair
        risk = float(ext.get("risk_score", 0) or 0)
        has_obj = 1 if (ext.get("objections") or []) else 0
        has_sig = 1 if (ext.get("decision_signals") or []) else 0
        scored.append((risk + 0.3 * has_obj + 0.2 * has_sig, i, pair))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = sorted(scored[:max_segments], key=lambda t: t[1])

    lines: list[str] = []
    catalog: list[dict] = []
    for _score, idx, pair in top:
        if isinstance(pair, dict) and "extraction" in pair:
            ext = pair.get("extraction", {})
            seg = pair.get("segment", {})
            ts = ext.get("timestamp") or seg.get("timestamp_str") or ""
            transcript = seg.get("transcript") or pair.get("transcript", "")
        else:
            ext = pair
            ts = pair.get("timestamp", "")
            transcript = pair.get("transcript", "")

        topic = ext.get("topic", "")
        risk = ext.get("risk", "")
        risk_score = ext.get("risk_score", 0)
        objs = ext.get("objections", []) or []
        sigs = ext.get("decision_signals", []) or []

        lines.append(
            f"[{ts}] topic={topic} risk={risk}({risk_score:.2f})"
            + (f" objections={objs}" if objs else "")
            + (f" decision_signals={sigs}" if sigs else "")
            + (f"\n    transcript: {transcript[:220]}" if transcript else "")
        )
        catalog.append({
            "segment_index": idx,
            "timestamp": ts,
            "topic": topic,
            "risk_score": risk_score,
        })

    return "\n".join(lines), catalog


def _parse_citations(text: str, catalog: list[dict]) -> list[dict]:
    """Pull [ts=MM:SS] markers out of an LLM response and match them to segments."""
    import re
    found: list[dict] = []
    ts_re = re.compile(r"\[ts=([0-9:]+)\]")
    for m in ts_re.finditer(text):
        raw_ts = m.group(1)
        match = next(
            (c for c in catalog if c["timestamp"].endswith(raw_ts) or c["timestamp"] == raw_ts),
            None,
        )
        if match:
            found.append(match)
    # Deduplicate by timestamp while preserving order.
    seen: set[str] = set()
    deduped = []
    for c in found:
        key = c["timestamp"]
        if key not in seen:
            deduped.append(c)
            seen.add(key)
    return deduped


async def _get_sf():
    from ...db.session import get_session_factory
    return get_session_factory()


async def _get_or_create_conversation(
    conversation_id: Optional[str], job_id: str, user_id: Optional[str], tenant_id: Optional[str]
) -> str:
    """Ensure a conversation row exists; return its id. Best-effort — returns a
    fresh UUID even if persistence fails."""
    if conversation_id:
        return conversation_id

    cid = str(uuid.uuid4())
    sf = await _get_sf()
    if sf is None:
        return cid
    try:
        from ...db.models import Conversation
        async with sf() as sess:
            sess.add(Conversation(
                id=cid, job_id=job_id, user_id=user_id, tenant_id=tenant_id,
                title="",
            ))
            await sess.commit()
    except Exception as exc:  # pragma: no cover — non-fatal
        logger.debug("conversation persist skipped: %s", exc)
    return cid


async def _persist_message(
    conversation_id: str,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    model: str | None = None,
    latency_ms: int | None = None,
) -> None:
    sf = await _get_sf()
    if sf is None:
        return
    try:
        from ...db.models import ChatMessage
        async with sf() as sess:
            sess.add(ChatMessage(
                conversation_id=conversation_id,
                role=role,
                content=content,
                citations=citations or [],
                model=model,
                latency_ms=latency_ms,
            ))
            await sess.commit()
    except Exception as exc:  # pragma: no cover
        logger.debug("message persist skipped: %s", exc)


async def _recent_messages(conversation_id: str, limit: int = 12) -> list[dict]:
    sf = await _get_sf()
    if sf is None:
        return []
    try:
        from ...db.models import ChatMessage
        from sqlalchemy import select
        async with sf() as sess:
            rows = (await sess.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.id.desc())
                .limit(limit)
            )).scalars().all()
        rows = list(reversed(rows))
        return [{"role": r.role, "content": r.content} for r in rows]
    except Exception:
        return []


# ── Request/Response models ────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None


# ── Non-streaming endpoint ─────────────────────────────────────────────────────

@router.post("/{job_id}/ask")
async def ask_question(job_id: str, req: AskRequest) -> dict:
    """One-shot JSON answer with citations. Persists user + assistant messages."""
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    conv_id = await _get_or_create_conversation(
        req.conversation_id, job_id, req.user_id, req.tenant_id,
    )
    await _persist_message(conv_id, "user", req.question)

    context, catalog = _build_segment_context(job)
    history = await _recent_messages(conv_id, limit=10)

    start = time.monotonic()
    answer, model_name = await _generate_answer(req.question, context, history)
    latency_ms = int((time.monotonic() - start) * 1000)

    citations = _parse_citations(answer, catalog)
    await _persist_message(
        conv_id, "assistant", answer,
        citations=citations, model=model_name, latency_ms=latency_ms,
    )

    return {
        "conversation_id": conv_id,
        "question": req.question,
        "answer": answer,
        "citations": citations,
        "model": model_name,
        "latency_ms": latency_ms,
    }


# ── SSE streaming endpoint ─────────────────────────────────────────────────────

@router.get("/{job_id}/stream")
async def stream_answer(
    job_id: str,
    q: str = Query(..., description="The question to ask"),
    conversation_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
) -> StreamingResponse:
    """Server-Sent Events. Emits:
      event: meta       — {"conversation_id", "citations_catalog"}
      event: token      — {"delta": "..."} (streamed tokens)
      event: citations  — {"citations": [...]} (final resolved)
      event: done       — {"latency_ms", "model"}
      event: error      — {"message"}
    """
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    conv_id = await _get_or_create_conversation(conversation_id, job_id, user_id, tenant_id)
    await _persist_message(conv_id, "user", q)

    context, catalog = _build_segment_context(job)
    history = await _recent_messages(conv_id, limit=10)

    async def gen():
        yield _sse("meta", {"conversation_id": conv_id, "citations_catalog": catalog})
        start = time.monotonic()
        collected = []
        model_name = "mock"
        try:
            async for token, m_name in _stream_answer(q, context, history):
                if m_name:
                    model_name = m_name
                if token:
                    collected.append(token)
                    yield _sse("token", {"delta": token})
        except Exception as exc:  # pragma: no cover — defensive
            yield _sse("error", {"message": str(exc)})
            return

        full = "".join(collected)
        citations = _parse_citations(full, catalog)
        latency_ms = int((time.monotonic() - start) * 1000)
        await _persist_message(
            conv_id, "assistant", full,
            citations=citations, model=model_name, latency_ms=latency_ms,
        )
        yield _sse("citations", {"citations": citations})
        yield _sse("done", {"latency_ms": latency_ms, "model": model_name})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Conversation history endpoints ─────────────────────────────────────────────

@router.get("/{job_id}/conversations")
async def list_conversations(job_id: str) -> dict:
    sf = await _get_sf()
    if sf is None:
        return {"conversations": []}
    try:
        from ...db.models import Conversation
        from sqlalchemy import select
        async with sf() as sess:
            rows = (await sess.execute(
                select(Conversation)
                .where(Conversation.job_id == job_id)
                .order_by(Conversation.updated_at.desc())
            )).scalars().all()
        return {
            "conversations": [
                {
                    "id": r.id, "title": r.title, "job_id": r.job_id,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rows
            ],
        }
    except Exception:
        return {"conversations": []}


@router.post("/{job_id}/voice")
async def voice_to_text(job_id: str, file: UploadFile = File(...)) -> dict:
    """Transcribe a short mic recording so the client can feed it as a chat question.

    Auto-detects the transcription backend:
    - ``faster-whisper`` (local, preferred) — works offline
    - OpenAI Whisper API (``OPENAI_API_KEY``) — fallback
    - Mock transcript (deterministic) — last-resort for dev/test
    """
    import os
    import tempfile

    jobs = _get_jobs()
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="job not found")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="empty audio payload")

    suffix = "." + (file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "webm")
    text: str = ""
    model_used = "mock"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]
            model_name = os.getenv("WHISPER_MODEL", "base")
            model = WhisperModel(model_name, device="auto", compute_type="auto")
            segments, _info = model.transcribe(tmp_path)
            text = " ".join(seg.text.strip() for seg in segments).strip()
            model_used = f"faster-whisper:{model_name}"
        except ImportError:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    from openai import OpenAI  # type: ignore[import-not-found]
                    client = OpenAI(api_key=api_key)
                    with open(tmp_path, "rb") as fh:
                        resp = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=fh,
                        )
                    text = (getattr(resp, "text", None) or "").strip()
                    model_used = "openai:whisper-1"
                except Exception as exc:  # pragma: no cover
                    logger.warning("OpenAI whisper fallback failed: %s", exc)
            if not text:
                text = "(voice transcription unavailable — configure faster-whisper or OPENAI_API_KEY)"
                model_used = "mock"
        except Exception as exc:  # pragma: no cover
            logger.warning("faster-whisper transcription failed: %s", exc)
            text = "(voice transcription failed)"
            model_used = "error"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return {"text": text, "model": model_used, "bytes": len(contents)}


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str) -> dict:
    sf = await _get_sf()
    if sf is None:
        return {"messages": []}
    try:
        from ...db.models import ChatMessage
        from sqlalchemy import select
        async with sf() as sess:
            rows = (await sess.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.id.asc())
            )).scalars().all()
        return {
            "messages": [
                {
                    "id": r.id, "role": r.role, "content": r.content,
                    "citations": r.citations or [],
                    "model": r.model, "latency_ms": r.latency_ms,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ],
        }
    except Exception:
        return {"messages": []}


# ── LLM generation (OpenAI if available, mock otherwise) ───────────────────────

def _llm_messages(question: str, context: str, history: list[dict]) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    msgs.append({
        "role": "system",
        "content": (
            "Deal segment timeline (redacted to high-signal parts):\n" + context
        ),
    })
    for h in history[-8:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": question})
    return msgs


async def _generate_answer(
    question: str, context: str, history: list[dict]
) -> tuple[str, str]:
    """Returns (answer_text, model_name). Falls back to a deterministic
    mock answer if the OpenAI client is unavailable."""
    try:
        from ...config import get_settings
        settings = get_settings()
        api_key = getattr(settings, "openai_api_key", None)
        if not api_key:
            return _mock_answer(question, context), "mock"
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=settings.openai.model,
            messages=_llm_messages(question, context, history),
            temperature=0.2,
            max_tokens=800,
        )
        return resp.choices[0].message.content or "", settings.openai.model
    except Exception as exc:
        logger.debug("chat llm fallback: %s", exc)
        return _mock_answer(question, context), "mock"


async def _stream_answer(
    question: str, context: str, history: list[dict]
):
    """Async generator yielding (token, model_name) tuples."""
    try:
        from ...config import get_settings
        settings = get_settings()
        api_key = getattr(settings, "openai_api_key", None)
        if not api_key:
            # Stream the mock answer word-by-word for a nice UX.
            text = _mock_answer(question, context)
            for word in text.split(" "):
                yield word + " ", "mock"
                await asyncio.sleep(0.01)
            return

        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        stream = await asyncio.to_thread(
            client.chat.completions.create,
            model=settings.openai.model,
            messages=_llm_messages(question, context, history),
            temperature=0.2,
            max_tokens=800,
            stream=True,
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content or ""
            except Exception:
                delta = ""
            if delta:
                yield delta, settings.openai.model
    except Exception as exc:
        logger.debug("stream llm fallback: %s", exc)
        text = _mock_answer(question, context)
        for word in text.split(" "):
            yield word + " ", "mock"
            await asyncio.sleep(0.01)


def _mock_answer(question: str, context: str) -> str:
    """Deterministic fallback — surfaces the most relevant lines from context
    with embedded timestamp citations so the frontend can render citations
    even without an LLM key.
    """
    if not context.strip():
        return "I don't have any analyzed segments for this deal yet."

    q_terms = {w.lower() for w in question.split() if len(w) > 3}
    lines = context.splitlines()
    picked: list[str] = []
    for line in lines:
        tokens = {w.lower() for w in line.split() if len(w) > 3}
        if q_terms & tokens:
            picked.append(line)
    if not picked:
        picked = lines[:3]

    bullets = []
    for line in picked[:4]:
        ts_start = line.find("[")
        ts_end = line.find("]")
        ts = line[ts_start + 1:ts_end] if ts_start >= 0 and ts_end > ts_start else ""
        body = line[ts_end + 1:].strip() if ts_end >= 0 else line
        bullets.append(f"- {body[:260]} [ts={ts}]")

    return (
        f"Based on the deal timeline, here's what stands out for your question "
        f"\u201c{question}\u201d:\n\n" + "\n".join(bullets)
    )
