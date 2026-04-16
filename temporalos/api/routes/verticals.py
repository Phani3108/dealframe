"""Vertical pack routes — list available packs, inspect schema, prompt hints,
and aggregate per-vertical dashboard metrics.

Packs v2: surface each pack's pack-specific prompt hint and dashboard metrics
so the UI can render vertical-aware analytics without bespoke endpoints.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from ...verticals import get_default_vertical_registry

router = APIRouter(prefix="/verticals", tags=["verticals"])


# Pack-specific prompt hints — lightweight guidance shown to the extraction
# layer (and the user) when a pack is active. Kept here (rather than on each
# pack subclass) so product can iterate without touching the core library.
_PROMPT_HINTS: Dict[str, str] = {
    "sales": (
        "Focus on pricing mentions, competitor callouts, champion identification, "
        "deal-stage signals, and urgency language. Flag missing next-steps as a risk."
    ),
    "procurement": (
        "Prioritise BATNA strength, bargaining tactics, issues on the table, "
        "escalation level, and integrative vs distributive signals. Score power balance."
    ),
    "customer_success": (
        "Detect churn precursors, adoption blockers, feature gaps, expansion hooks, "
        "and renewal timing. Elevate product-feedback requests to top-level fields."
    ),
    "real_estate": (
        "Extract property details, buyer motivations, contingencies, financing signals, "
        "and competitive-offer context. Surface inspection and appraisal concerns."
    ),
    "ux_research": (
        "Capture user tasks, pain points, mental models, and severity of usability issues. "
        "Ignore sales-specific framings; value direct user quotes highly."
    ),
}


def _vertical_of_job(job: Dict[str, Any]) -> str:
    """Best-effort detection of the vertical used for a given job record."""
    return (
        (job.get("vertical") or "").lower()
        or (job.get("result", {}).get("vertical") or "").lower()
        or "sales"
    )


@router.get("")
async def list_packs() -> Dict[str, Any]:
    reg = get_default_vertical_registry()
    packs: List[Dict[str, Any]] = []
    for p in reg.list_packs():
        d = p.to_dict()
        d["prompt_hint"] = _PROMPT_HINTS.get(p.id, "")
        packs.append(d)
    return {"packs": packs, "total": len(packs)}


@router.get("/{pack_id}")
async def get_pack(pack_id: str) -> Dict[str, Any]:
    reg = get_default_vertical_registry()
    pack = reg.get(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Unknown vertical: {pack_id}")
    d = pack.to_dict()
    d["prompt_hint"] = _PROMPT_HINTS.get(pack_id, "")
    return d


@router.get("/{pack_id}/dashboard")
async def pack_dashboard(pack_id: str, limit: int = 200) -> Dict[str, Any]:
    """Return aggregated metrics for deals processed under this pack.

    Metrics are computed client-side from the in-memory job store — no new
    infra required, and the output is stable enough for visualisation.
    """
    reg = get_default_vertical_registry()
    pack = reg.get(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Unknown vertical: {pack_id}")

    from ...api.routes.process import _jobs

    matched: List[Dict[str, Any]] = []
    for job in list(_jobs.values())[-limit:]:
        if _vertical_of_job(job) == pack_id:
            matched.append(job)

    if not matched:
        return {
            "pack_id": pack_id,
            "deal_count": 0,
            "avg_risk": 0.0,
            "high_risk_rate": 0.0,
            "top_topics": [],
            "top_objections": [],
            "pack_fields": [f["name"] for f in pack.schema().to_dict()["fields"]],
        }

    risk_total = 0.0
    high_risk = 0
    total_segments = 0
    topic_counts: Counter[str] = Counter()
    objection_counts: Counter[str] = Counter()
    # Pack-specific field counters (e.g. pricing_mentions for sales)
    extra_field_hits: Counter[str] = Counter()

    for job in matched:
        intel = job.get("result") or {}
        risk_total += float(intel.get("overall_risk_score") or 0.0)
        segs = intel.get("segments") or []
        total_segments += len(segs)
        for pair in segs:
            ext = pair.get("extraction") or {}
            if (ext.get("risk_score") or 0) > 0.6:
                high_risk += 1
            if ext.get("topic"):
                topic_counts[str(ext["topic"])] += 1
            for obj in ext.get("objections") or []:
                objection_counts[str(obj).lower()[:60]] += 1
            for fname in pack.schema().to_dict()["fields"]:
                name = fname["name"]
                val = ext.get(name)
                if isinstance(val, list) and val:
                    extra_field_hits[name] += len(val)
                elif isinstance(val, bool) and val:
                    extra_field_hits[name] += 1

    deal_count = len(matched)
    return {
        "pack_id": pack_id,
        "deal_count": deal_count,
        "total_segments": total_segments,
        "avg_risk": risk_total / deal_count if deal_count else 0.0,
        "high_risk_rate": (high_risk / total_segments) if total_segments else 0.0,
        "top_topics": topic_counts.most_common(8),
        "top_objections": objection_counts.most_common(8),
        "pack_field_hits": extra_field_hits.most_common(10),
        "pack_fields": [f["name"] for f in pack.schema().to_dict()["fields"]],
        "prompt_hint": _PROMPT_HINTS.get(pack_id, ""),
    }
