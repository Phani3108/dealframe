"""Scoped, signed share links for read-only deal views + public brief export.

Links are opaque UUIDs recorded in the ``share_links`` table with optional TTL
and a revoked flag. The ``GET /share/view/{token}`` endpoint intentionally
requires no auth — it's the public guest view — but still validates the token
against the DB and increments a view counter.

The export endpoint produces a one-page HTML brief that can be printed to
PDF client-side or saved as-is. We avoid a hard dep on ``weasyprint`` to keep
the install light; clients can ``@media print`` the HTML.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["share"])


async def _sf():
    from ...db.session import get_session_factory
    return get_session_factory()


class ShareRequest(BaseModel):
    job_id: str
    ttl_hours: Optional[int] = 168  # 1 week
    tenant_id: Optional[str] = None
    created_by: Optional[str] = None


def _link_dict(row, base_url: str = "") -> dict:
    url = f"{base_url.rstrip('/')}/shared/{row.id}" if base_url else f"/shared/{row.id}"
    return {
        "id": row.id,
        "job_id": row.job_id,
        "url": url,
        "scope": row.scope,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "revoked": row.revoked,
        "view_count": row.view_count,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/share")
async def create_share_link(req: ShareRequest, request: Request) -> dict:
    from .process import _jobs
    if req.job_id not in _jobs:
        raise HTTPException(404, f"Job '{req.job_id}' not found")

    sf = await _sf()
    if sf is None:
        raise HTTPException(503, "Database not available")

    from ...db.models import ShareLink
    token = uuid.uuid4().hex
    expires = None
    if req.ttl_hours and req.ttl_hours > 0:
        expires = datetime.utcnow() + timedelta(hours=req.ttl_hours)

    async with sf() as sess:
        row = ShareLink(
            id=token,
            job_id=req.job_id,
            tenant_id=req.tenant_id,
            created_by=req.created_by,
            scope="readonly",
            expires_at=expires,
            revoked=False,
        )
        sess.add(row)
        await sess.commit()
        await sess.refresh(row)

    base_url = str(request.base_url).rstrip("/")
    return {"link": _link_dict(row, base_url)}


@router.get("/share")
async def list_share_links(job_id: Optional[str] = Query(None)) -> dict:
    sf = await _sf()
    if sf is None:
        return {"links": []}
    from ...db.models import ShareLink
    from sqlalchemy import select
    async with sf() as sess:
        stmt = select(ShareLink).order_by(ShareLink.created_at.desc())
        if job_id:
            stmt = stmt.where(ShareLink.job_id == job_id)
        rows = (await sess.execute(stmt)).scalars().all()
    return {"links": [_link_dict(r) for r in rows]}


@router.delete("/share/{link_id}")
async def revoke_share_link(link_id: str) -> dict:
    sf = await _sf()
    if sf is None:
        raise HTTPException(503, "Database not available")
    from ...db.models import ShareLink
    from sqlalchemy import select
    async with sf() as sess:
        row = (await sess.execute(
            select(ShareLink).where(ShareLink.id == link_id)
        )).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "Link not found")
        row.revoked = True
        await sess.commit()
    return {"revoked": True}


@router.get("/share/view/{token}")
async def view_shared_deal(token: str) -> dict:
    """Public guest view. Returns the minimal deal payload — no auth required."""
    sf = await _sf()
    if sf is None:
        raise HTTPException(503, "Database not available")
    from ...db.models import ShareLink
    from sqlalchemy import select
    async with sf() as sess:
        row = (await sess.execute(
            select(ShareLink).where(ShareLink.id == token)
        )).scalar_one_or_none()
        if row is None or row.revoked:
            raise HTTPException(404, "Link not found or revoked")
        if row.expires_at and row.expires_at < datetime.utcnow():
            raise HTTPException(410, "Link expired")
        row.view_count = (row.view_count or 0) + 1
        await sess.commit()
        job_id = row.job_id
        expires = row.expires_at.isoformat() if row.expires_at else None

    from .process import _jobs
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Deal not available")
    return {
        "job_id": job_id,
        "title": f"Deal {job_id[:8]}",
        "result": job.get("result") or {},
        "expires_at": expires,
    }


# ── Deal brief (printable HTML) ────────────────────────────────────────────────

@router.get("/export/brief/{job_id}", response_class=HTMLResponse)
async def deal_brief_html(job_id: str) -> HTMLResponse:
    """One-page HTML deal brief. Browser → ⌘P → save as PDF."""
    from .process import _jobs
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    intel = job.get("result") or {}
    segments = intel.get("segments", [])
    overall = intel.get("overall_risk_score", 0)
    high_risk = [s for s in segments if (s.get("extraction", {}) if "extraction" in s else s).get("risk") == "high"]
    objections: list[str] = []
    signals: list[str] = []
    for s in segments:
        ext = s.get("extraction") if isinstance(s, dict) and "extraction" in s else s
        objections.extend(ext.get("objections") or [])
        signals.extend(ext.get("decision_signals") or [])
    obj_top = _top_k(objections, 6)
    sig_top = _top_k(signals, 6)

    rows_html = "\n".join(
        f"""
        <tr>
          <td class="ts">{(s.get('extraction') if isinstance(s, dict) and 'extraction' in s else s).get('timestamp','')}</td>
          <td class="topic">{(s.get('extraction') if isinstance(s, dict) and 'extraction' in s else s).get('topic','')}</td>
          <td class="risk risk-{(s.get('extraction') if isinstance(s, dict) and 'extraction' in s else s).get('risk','low')}">
            {int(100 * float((s.get('extraction') if isinstance(s, dict) and 'extraction' in s else s).get('risk_score', 0) or 0))}%
          </td>
        </tr>"""
        for s in segments[:30]
    )

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Deal Brief — {job_id[:8]}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 40px; color: #0f172a; }}
  h1 {{ font-size: 28px; margin: 0 0 4px 0; }}
  .sub {{ color: #64748b; font-size: 12px; margin-bottom: 28px; }}
  .row {{ display: flex; gap: 40px; margin: 20px 0; }}
  .stat {{ flex: 1; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 18px; }}
  .stat .label {{ font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.12em; font-weight: 700; }}
  .stat .value {{ font-size: 26px; font-weight: 700; margin-top: 6px; tabular-nums: true; }}
  .high {{ color: #dc2626; }}
  h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.1em; color: #475569; margin: 28px 0 10px 0; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
  ul {{ margin: 0; padding-left: 18px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }}
  th, td {{ padding: 6px 8px; text-align: left; border-bottom: 1px solid #f1f5f9; }}
  th {{ font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.1em; }}
  td.ts {{ font-family: monospace; color: #6366f1; width: 80px; }}
  td.topic {{ text-transform: capitalize; }}
  td.risk {{ text-align: right; width: 80px; font-weight: 700; tabular-nums: true; }}
  .risk-high {{ color: #dc2626; }}
  .risk-medium {{ color: #d97706; }}
  .risk-low {{ color: #059669; }}
  @media print {{ body {{ margin: 20px; }} }}
</style>
</head>
<body>
  <h1>Deal Brief</h1>
  <p class="sub">DealFrame · {job_id} · Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
  <div class="row">
    <div class="stat">
      <div class="label">Overall Risk</div>
      <div class="value {'high' if overall > 0.6 else ''}">{int(100 * float(overall))}%</div>
    </div>
    <div class="stat">
      <div class="label">High-risk segments</div>
      <div class="value {'high' if high_risk else ''}">{len(high_risk)}</div>
    </div>
    <div class="stat">
      <div class="label">Total segments</div>
      <div class="value">{len(segments)}</div>
    </div>
  </div>

  <h2>Top Objections</h2>
  {'<ul>' + ''.join(f'<li>{o[0]} <span style=\"color:#94a3b8\">×{o[1]}</span></li>' for o in obj_top) + '</ul>' if obj_top else '<p style="color:#94a3b8">None detected.</p>'}

  <h2>Decision Signals</h2>
  {'<ul>' + ''.join(f'<li>{s[0]} <span style=\"color:#94a3b8\">×{s[1]}</span></li>' for s in sig_top) + '</ul>' if sig_top else '<p style="color:#94a3b8">None detected.</p>'}

  <h2>Timeline</h2>
  <table>
    <thead><tr><th>Time</th><th>Topic</th><th>Risk</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body></html>"""
    return HTMLResponse(html)


def _top_k(items: list[str], k: int) -> list[tuple[str, int]]:
    from collections import Counter
    return Counter(items).most_common(k)
