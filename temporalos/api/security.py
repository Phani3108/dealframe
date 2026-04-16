"""Tenant-scoped security helpers.

Provides a FastAPI dependency `tenant_guard` that can be mounted on any
router to enforce tenant presence + ownership without touching each
handler. Also exposes `enforce_tenant_on_job` for job-id routes.

Design:
- Controlled by the ``DEALFRAME_REQUIRE_TENANT`` env var.
- When disabled (default), the guard is a no-op — preserves current dev UX.
- When enabled, any call to ``/api/v1/*`` must carry an ``X-Tenant-ID`` header
  (or resolved subdomain). Routes that touch a specific job also assert the
  job belongs to the caller's tenant.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, Request


def require_tenant_enabled() -> bool:
    return os.environ.get("DEALFRAME_REQUIRE_TENANT", "").lower() in {"1", "true", "yes"}


async def tenant_guard(
    request: Request,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
) -> Optional[str]:
    """FastAPI dependency — ensures a tenant header is present when required.

    Returns the resolved tenant id (or ``None`` when enforcement is off).
    The tenant is stashed on ``request.state.tenant_id`` for downstream use.
    """
    tenant_id: Optional[str] = x_tenant_id

    if not tenant_id:
        # Fallback to context set by TenantMiddleware (subdomain / slug).
        try:
            from ..enterprise.multi_tenant import get_tenant
            ctx = get_tenant()
            if ctx is not None:
                tenant_id = ctx.tenant_id
        except Exception:
            tenant_id = None

    if require_tenant_enabled() and not tenant_id:
        raise HTTPException(status_code=401, detail="tenant required — supply X-Tenant-ID header")

    request.state.tenant_id = tenant_id
    return tenant_id


def enforce_tenant_on_job(job: dict, tenant_id: Optional[str]) -> None:
    """Ensure the caller's tenant owns the job record.

    Safely tolerates legacy records that have no ``tenant_id`` by allowing access
    when enforcement is disabled; raises 404 (not 403) when enforcement is on so
    we don't leak the existence of other tenants' records.
    """
    if not require_tenant_enabled():
        return

    job_tenant = job.get("tenant_id") if isinstance(job, dict) else getattr(job, "tenant_id", None)
    if job_tenant and tenant_id and job_tenant != tenant_id:
        raise HTTPException(status_code=404, detail="not found")
    if job_tenant and not tenant_id:
        raise HTTPException(status_code=401, detail="tenant required")
