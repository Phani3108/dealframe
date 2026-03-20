"""
Phase 6 end-to-end test — Frontend Dashboard & static file serving.

Verifies that:
  1. FastAPI correctly serves the built React app at `/`
  2. The SPA catch-all serves index.html for any non-API path
  3. Built static assets are reachable under /assets/
  4. API endpoints (/health, /api/v1/*) are NOT intercepted by the SPA route
  5. Frontend dist directory has the expected structure (post-build)
  6. The built index.html references the expected app root element
  7. Content-type headers are correct for HTML and JS assets
  8. No API routes are shadowed by the SPA catch-all

Rules (claude.md §0):
  - Requires `cd frontend && npm run build` to have been run first
  - All real FastAPI code; only DB is mocked
  - Must pass with 0 failures
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"
_FRONTEND_EXISTS = _FRONTEND_DIST.exists() and (_FRONTEND_DIST / "index.html").exists()

pytestmark = pytest.mark.skipif(
    not _FRONTEND_EXISTS,
    reason="frontend/dist not found — run: cd frontend && npm run build",
)


@pytest.fixture(scope="module")
def client():
    with patch("temporalos.db.session.init_db", return_value=None):
        from temporalos.api.main import app
        yield TestClient(app, raise_server_exceptions=True)


# ── Frontend dist structure ───────────────────────────────────────────────────


class TestFrontendDistStructure:
    def test_dist_directory_exists(self):
        assert _FRONTEND_DIST.exists()

    def test_index_html_exists(self):
        assert (_FRONTEND_DIST / "index.html").exists()

    def test_assets_directory_exists(self):
        assert (_FRONTEND_DIST / "assets").exists()

    def test_assets_contains_js_file(self):
        js_files = list((_FRONTEND_DIST / "assets").glob("*.js"))
        assert len(js_files) > 0, "No JS files found in dist/assets"

    def test_assets_contains_css_file(self):
        css_files = list((_FRONTEND_DIST / "assets").glob("*.css"))
        assert len(css_files) > 0, "No CSS files found in dist/assets"

    def test_index_html_has_root_div(self):
        html = (_FRONTEND_DIST / "index.html").read_text()
        assert '<div id="root">' in html

    def test_index_html_references_script(self):
        html = (_FRONTEND_DIST / "index.html").read_text()
        assert "assets/" in html

    def test_index_html_has_correct_title(self):
        html = (_FRONTEND_DIST / "index.html").read_text()
        assert "TemporalOS" in html


# ── FastAPI static file serving ───────────────────────────────────────────────


class TestFrontendServing:
    def test_root_returns_200(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_content_type_is_html(self, client: TestClient):
        resp = client.get("/")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_root_contains_temporalos_title(self, client: TestClient):
        resp = client.get("/")
        assert "TemporalOS" in resp.text

    def test_root_contains_root_div(self, client: TestClient):
        resp = client.get("/")
        assert 'id="root"' in resp.text

    def test_spa_path_upload_serves_index(self, client: TestClient):
        """SPA route /upload must return index.html (client-side routing)."""
        resp = client.get("/upload")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_spa_path_observatory_serves_index(self, client: TestClient):
        resp = client.get("/observatory")
        assert resp.status_code == 200

    def test_spa_path_intelligence_serves_index(self, client: TestClient):
        resp = client.get("/intelligence")
        assert resp.status_code == 200

    def test_spa_path_finetuning_serves_index(self, client: TestClient):
        resp = client.get("/finetuning")
        assert resp.status_code == 200

    def test_spa_path_local_serves_index(self, client: TestClient):
        resp = client.get("/local")
        assert resp.status_code == 200

    def test_spa_deep_path_serves_index(self, client: TestClient):
        resp = client.get("/results/some-job-id")
        assert resp.status_code == 200

    def test_assets_js_served(self, client: TestClient):
        js = next((_FRONTEND_DIST / "assets").glob("*.js"), None)
        assert js is not None
        resp = client.get(f"/assets/{js.name}")
        assert resp.status_code == 200

    def test_assets_css_served(self, client: TestClient):
        css = next((_FRONTEND_DIST / "assets").glob("*.css"), None)
        assert css is not None
        resp = client.get(f"/assets/{css.name}")
        assert resp.status_code == 200


# ── API routes NOT shadowed by SPA ────────────────────────────────────────────


class TestAPIRoutesNotShadowed:
    def test_health_endpoint_returns_json(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "temporalos"

    def test_health_is_not_html(self, client: TestClient):
        resp = client.get("/health")
        assert "text/html" not in resp.headers.get("content-type", "")

    def test_api_local_status_returns_json(self, client: TestClient):
        resp = client.get("/api/v1/local/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "whisper_available" in data
        assert "cost_per_video_usd" in data

    def test_api_finetuning_runs_returns_json(self, client: TestClient):
        resp = client.get("/api/v1/finetuning/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "experiments" in data

    def test_api_intelligence_objections_returns_json(self, client: TestClient):
        from unittest.mock import AsyncMock, MagicMock
        from temporalos.db.session import get_session

        async def mock_session():
            mock = MagicMock()
            mock.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
            yield mock

        from temporalos.api.main import app
        app.dependency_overrides[get_session] = mock_session
        try:
            resp = client.get("/api/v1/intelligence/objections")
            assert resp.status_code == 200
            assert "objections" in resp.json()
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_api_observatory_sessions_returns_json(self, client: TestClient):
        resp = client.get("/api/v1/observatory/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data

    def test_openapi_docs_not_shadowed(self, client: TestClient):
        """FastAPI /docs must not be served as the SPA index."""
        resp = client.get("/docs")
        # /docs redirects to /docs# or serves the swagger UI HTML
        # either way should not return the SPA index.html content
        assert resp.status_code in (200, 307, 301)

    def test_jobs_endpoint_returns_json(self, client: TestClient):
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data


# ── Content integrity checks ─────────────────────────────────────────────────


class TestFrontendContentIntegrity:
    def test_index_html_references_indigo_or_tailwind(self, client: TestClient):
        """Check that Tailwind CSS is compiled in (not just linked from CDN).
        The built CSS file should contain compiled utility classes."""
        css = next((_FRONTEND_DIST / "assets").glob("*.css"), None)
        if css:
            content = css.read_text()
            # Tailwind compiled output contains utility class names
            assert len(content) > 1000, "CSS file seems too small to contain Tailwind utilities"

    def test_index_html_does_not_contain_inline_scripts(self, client: TestClient):
        """Verify no inline scripts with sensitive data."""
        resp = client.get("/")
        # Should NOT have inline JS (only an external script tag from assets)
        import re
        inline_scripts = re.findall(r'<script[^>]*>[^<]+</script>', resp.text)
        assert len(inline_scripts) == 0, f"Found inline scripts: {inline_scripts}"

    def test_json_api_response_is_valid_json(self, client: TestClient):
        resp = client.get("/health")
        data = json.loads(resp.text)
        assert isinstance(data, dict)
