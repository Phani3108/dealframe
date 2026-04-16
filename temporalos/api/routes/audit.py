"""Audit Trail API routes — query, search, and export audit logs."""
from __future__ import annotations

import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/audit", tags=["audit"])


def _filter_entries(entries, *, since: float | None, until: float | None, q: str):
    if since is not None:
        entries = [e for e in entries if e.timestamp >= since]
    if until is not None:
        entries = [e for e in entries if e.timestamp <= until]
    if q:
        needle = q.lower()
        entries = [
            e for e in entries
            if needle in (e.action or "").lower()
            or needle in (e.resource_type or "").lower()
            or needle in (e.resource_id or "").lower()
            or needle in (e.user_id or "").lower()
            or needle in json.dumps(e.details or {}).lower()
        ]
    return entries


@router.get("")
async def query_audit(
    user_id: str = Query("", description="Filter by user"),
    tenant_id: str = Query("", description="Filter by tenant"),
    action: str = Query("", description="Filter by action"),
    resource_type: str = Query("", description="Filter by resource type"),
    since: Optional[float] = Query(None, description="Unix timestamp — earliest to include"),
    until: Optional[float] = Query(None, description="Unix timestamp — latest to include"),
    q: str = Query("", description="Full-text search across action/resource/details"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    from ...enterprise.audit import get_audit_trail
    trail = get_audit_trail()
    # Query a wider slice then apply advanced filters client-side in the route.
    base = trail.query(
        user_id=user_id, tenant_id=tenant_id,
        action=action, resource_type=resource_type,
        limit=10_000, offset=0,
    )
    filtered = _filter_entries(base, since=since, until=until, q=q)
    total = len(filtered)
    page = filtered[offset:offset + limit]
    return {
        "entries": [e.to_dict() for e in page],
        "total": total,
        "total_unfiltered": trail.count(tenant_id),
        "limit": limit,
        "offset": offset,
    }


@router.get("/export")
async def export_audit(
    user_id: str = Query(""),
    tenant_id: str = Query(""),
    action: str = Query(""),
    resource_type: str = Query(""),
    since: Optional[float] = Query(None),
    until: Optional[float] = Query(None),
    q: str = Query(""),
    fmt: str = Query("csv", pattern="^(csv|json)$"),
) -> StreamingResponse:
    """Export the current filter slice as CSV or JSON."""
    from ...enterprise.audit import get_audit_trail
    trail = get_audit_trail()
    base = trail.query(
        user_id=user_id, tenant_id=tenant_id,
        action=action, resource_type=resource_type,
        limit=100_000, offset=0,
    )
    filtered = _filter_entries(base, since=since, until=until, q=q)

    if fmt == "json":
        payload = json.dumps([e.to_dict() for e in filtered], default=str, indent=2)
        return StreamingResponse(
            iter([payload]),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="audit.json"'},
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "timestamp", "user_id", "tenant_id", "action",
        "resource_type", "resource_id", "ip_address", "details",
    ])
    for e in filtered:
        writer.writerow([
            e.id,
            e.timestamp,
            e.user_id,
            e.tenant_id,
            e.action,
            e.resource_type,
            e.resource_id,
            e.ip_address,
            json.dumps(e.details or {}, default=str),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit.csv"'},
    )


@router.get("/stats")
async def audit_stats(tenant_id: str = Query("")) -> dict:
    from ...enterprise.audit import get_audit_trail
    trail = get_audit_trail()
    entries = trail.query(tenant_id=tenant_id, limit=10000)
    action_counts: dict[str, int] = {}
    resource_counts: dict[str, int] = {}
    for e in entries:
        action_counts[e.action] = action_counts.get(e.action, 0) + 1
        resource_counts[e.resource_type] = resource_counts.get(e.resource_type, 0) + 1
    return {
        "total_entries": trail.count(tenant_id),
        "action_counts": action_counts,
        "resource_counts": resource_counts,
    }
