"""Agents API routes — Q&A, Risk, Coaching, Knowledge Graph, Meeting Prep."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


def _get_jobs() -> dict:
    from ...api.routes.process import _jobs  # type: ignore[attr-defined]
    return _jobs


# ─────────────────────────────── Q&A ─────────────────────────────────────────

@router.get("/qa")
async def video_qa(
    q: str = Query(..., description="Natural language question"),
    job_id: Optional[str] = Query(None, description="Limit to a specific job"),
) -> dict:
    """Answer a natural-language question over the indexed video library."""
    from ...agents.qa_agent import get_qa_agent
    agent = get_qa_agent()
    answer = agent.ask(q, filter_job_id=job_id)
    return answer.to_dict()


@router.post("/qa/index/{job_id}")
async def index_job_for_qa(job_id: str) -> dict:
    """Index a completed job into the Q&A vector store."""
    from ...agents.qa_agent import get_qa_agent
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    intel = job.get("intelligence")
    if not intel:
        raise HTTPException(400, "No intelligence data for this job")

    agent = get_qa_agent()
    count = agent.index_job(job_id, intel)
    return {"job_id": job_id, "indexed_segments": count, "total_index_size": agent.index_size}


# ─────────────────────────────── Risk ────────────────────────────────────────

class RiskRecordRequest(BaseModel):
    company: str = ""
    deal_id: str = ""


@router.get("/risk/alerts")
async def get_risk_alerts() -> dict:
    """Return all current high-risk deal alerts."""
    from ...agents.risk_agent import get_risk_agent
    agent = get_risk_agent()
    alerts = agent.run_sweep()
    deals = agent.list_deals()
    return {"alerts": [a.to_dict() for a in alerts], "deals": deals}


@router.post("/risk/record/{job_id}")
async def record_risk(job_id: str, req: RiskRecordRequest) -> dict:
    """Record a job's risk to the deal risk agent and return any new alerts."""
    from ...agents.risk_agent import get_risk_agent
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    intel = job.get("intelligence", {})

    agent = get_risk_agent()
    alerts = agent.record_job(job_id, intel, req.company, req.deal_id)
    return {"job_id": job_id, "alerts": [a.to_dict() for a in alerts]}


@router.get("/risk/deal")
async def get_deal_summary(company: str = Query(...),
                            deal_id: str = Query("")) -> dict:
    from ...agents.risk_agent import get_risk_agent
    agent = get_risk_agent()
    summary = agent.get_deal_summary(company, deal_id)
    if summary is None:
        raise HTTPException(404, f"No data for company '{company}'")
    return summary


# ─────────────────────────────── Coaching ────────────────────────────────────

class CoachingRecordRequest(BaseModel):
    rep_id: str
    speaker_label: str = "SPEAKER_A"


@router.get("/coaching/{rep_id}")
async def get_coaching_card(rep_id: str) -> dict:
    """Return a coaching card for a sales rep."""
    from ...agents.coaching import get_coaching_engine
    engine = get_coaching_engine()
    card = engine.generate_coaching_card(rep_id)
    if card is None:
        raise HTTPException(404, f"No data for rep '{rep_id}'")
    return card.to_dict()


@router.post("/coaching/record/{job_id}")
async def record_call_for_coaching(job_id: str, req: CoachingRecordRequest) -> dict:
    from ...agents.coaching import get_coaching_engine
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    intel = job.get("intelligence", {})

    engine = get_coaching_engine()
    engine.record_call(req.rep_id, job_id, intel, req.speaker_label)
    return {"recorded": True, "rep_id": req.rep_id, "job_id": job_id}


@router.get("/coaching")
async def list_reps() -> dict:
    from ...agents.coaching import get_coaching_engine
    return {"reps": get_coaching_engine().list_reps()}


# ─────────────────────────────── Knowledge Graph ─────────────────────────────

@router.get("/kg")
async def query_knowledge_graph(
    entity: str = Query(...),
    limit: int = Query(20, le=100),
) -> dict:
    from ...agents.knowledge_graph import get_knowledge_graph
    kg = get_knowledge_graph()
    return kg.query(entity, limit=limit)


@router.post("/kg/index/{job_id}")
async def index_job_in_kg(job_id: str) -> dict:
    from ...agents.knowledge_graph import get_knowledge_graph
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    intel = job.get("intelligence", job.get("result", {}))
    kg = get_knowledge_graph()
    count = kg.add_video(job_id, intel)

    # Persist nodes and edges to database
    try:
        from ...db.session import get_session_factory
        from ...db.models import KGNodeRecord, KGEdgeRecord
        from sqlalchemy import select
        sf = get_session_factory()
        if sf:
            async with sf() as sess:
                for node in kg._nodes.values():
                    row = (await sess.execute(
                        select(KGNodeRecord).where(KGNodeRecord.node_id == node.id)
                    )).scalar_one_or_none()
                    if row is None:
                        row = KGNodeRecord(node_id=node.id,
                                           entity_type=node.entity_type,
                                           label=node.label)
                        sess.add(row)
                    row.frequency = node.frequency
                    row.jobs = sorted(node.jobs)
                for edge in kg._edges.values():
                    edge_row = (await sess.execute(
                        select(KGEdgeRecord).where(
                            KGEdgeRecord.source == edge.source,
                            KGEdgeRecord.target == edge.target,
                        )
                    )).scalar_one_or_none()
                    if edge_row is None:
                        edge_row = KGEdgeRecord(source=edge.source, target=edge.target)
                        sess.add(edge_row)
                    edge_row.weight = edge.weight
                await sess.commit()
    except Exception as exc:
        logger.warning("KG persistence failed: %s", exc)

    return {"job_id": job_id, "entities_indexed": count, "stats": kg.stats}


@router.get("/kg/top")
async def kg_top_entities(
    entity_type: Optional[str] = None,
    limit: int = Query(20, le=100),
) -> dict:
    from ...agents.knowledge_graph import get_knowledge_graph
    return {"entities": get_knowledge_graph().top_entities(entity_type, limit)}


@router.get("/kg/export")
async def kg_export() -> dict:
    from ...agents.knowledge_graph import get_knowledge_graph
    return get_knowledge_graph().export_json()


# ─────────────────────────────── Meeting Prep ────────────────────────────────

class MeetingPrepRequest(BaseModel):
    company: str
    contact: str = ""


@router.post("/meeting-prep")
async def generate_meeting_brief(req: MeetingPrepRequest) -> dict:
    from ...agents.meeting_prep import get_meeting_prep_agent
    agent = get_meeting_prep_agent()
    brief = agent.generate_brief(req.company, req.contact)
    return brief.to_dict()


@router.post("/meeting-prep/index/{job_id}")
async def index_job_for_meeting_prep(job_id: str,
                                      company: str = "",
                                      contact: str = "") -> dict:
    from ...agents.meeting_prep import get_meeting_prep_agent
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    intel = job.get("intelligence", {})
    agent = get_meeting_prep_agent()
    agent.index_job(job_id, intel, company, contact)
    return {"indexed": True, "job_id": job_id, "company": company}


@router.get("/meeting-prep/companies")
async def list_indexed_companies() -> dict:
    from ...agents.meeting_prep import get_meeting_prep_agent
    return {"companies": get_meeting_prep_agent().indexed_companies}
