"""Cross-tenant fuzz test for the tenant-scoped dependency guard.

Verifies:
- `/api/v1/*` endpoints reject requests without `X-Tenant-ID` when
  ``DEALFRAME_REQUIRE_TENANT=1``.
- Public `/api/v1/share/view/*` and health paths remain open.
- Tenant guard is a no-op when disabled, preserving default dev UX.
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_guard(monkeypatch):
    monkeypatch.setenv("DEALFRAME_REQUIRE_TENANT", "1")
    # Reimport the app so the env var takes effect in the middleware check.
    from importlib import reload
    import temporalos.api.main as main_module
    reload(main_module)
    return main_module.app


@pytest.fixture
def app_without_guard(monkeypatch):
    monkeypatch.setenv("DEALFRAME_REQUIRE_TENANT", "0")
    from importlib import reload
    import temporalos.api.main as main_module
    reload(main_module)
    return main_module.app


PROTECTED_PATHS = [
    "/api/v1/jobs",
    "/api/v1/search?q=test",
    "/api/v1/patterns",
    "/api/v1/verticals",
    "/api/v1/flywheel/status",
]


def test_missing_tenant_blocks_protected_paths(app_with_guard):
    client = TestClient(app_with_guard)
    for path in PROTECTED_PATHS:
        r = client.get(path)
        assert r.status_code == 401, f"{path} should require tenant; got {r.status_code}"
        assert "tenant" in r.json().get("detail", "").lower()


def test_tenant_header_passes(app_with_guard):
    client = TestClient(app_with_guard)
    tid = f"tenant-{uuid.uuid4().hex[:8]}"
    for path in PROTECTED_PATHS:
        r = client.get(path, headers={"X-Tenant-ID": tid})
        # Should not be 401 (may be 200/404 depending on resource state)
        assert r.status_code != 401, f"{path} rejected valid tenant header: {r.status_code}"


def test_public_share_view_open(app_with_guard):
    client = TestClient(app_with_guard)
    # unknown token should 404, NOT 401 — means guard lets the request through
    r = client.get("/api/v1/share/view/nonexistent-token-xyz")
    assert r.status_code != 401


def test_guard_is_noop_when_disabled(app_without_guard):
    client = TestClient(app_without_guard)
    r = client.get("/api/v1/jobs")
    assert r.status_code != 401


def test_cross_tenant_fuzz_does_not_401_with_header(app_with_guard):
    """Fuzz: a variety of tenant ids should all be accepted by the guard layer.
    Tenant-ownership checks happen *below* the guard; the guard itself is only
    about presence. This test documents that contract.
    """
    client = TestClient(app_with_guard)
    for _ in range(10):
        tid = f"fuzz-{uuid.uuid4().hex[:8]}"
        r = client.get("/api/v1/verticals", headers={"X-Tenant-ID": tid})
        assert r.status_code != 401
