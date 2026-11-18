"""Regression tests for P0-2 & P0-3: Sidecar lifecycle, production auth by default, and docs protection."""

from __future__ import annotations

import subprocess
import sys
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import EngineConfig, settings
from app.main import create_app


@pytest.mark.asyncio
async def test_p0_production_auth_and_docs_protection() -> None:
    # 1. Enforce production mode
    orig_dev = settings.dev_mode
    orig_token = settings.auth_token
    try:
        settings.dev_mode = False
        settings.auth_token = "aksa-prod-token-xyz-9876543210"

        app = create_app()
        transport = ASGITransport(app=app)

        # 2. Unauthenticated request to protected endpoint -> 401
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp_teams_unauth = await client.get("/api/v1/teams")
            assert resp_teams_unauth.status_code == 401
            assert resp_teams_unauth.json()["code"] == "UNAUTHORIZED_SIDECAR_TOKEN"

            # 3. Unauthenticated request to /api/v1/health -> 200 (allowed for healthcheck)
            resp_health = await client.get("/api/v1/health")
            assert resp_health.status_code == 200

        # 4. Authenticated request with valid X-AKSA-Auth-Token -> 200
        auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}
        async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
            resp_teams_auth = await client.get("/api/v1/teams")
            assert resp_teams_auth.status_code == 200
            assert "teams" in resp_teams_auth.json()

            # Docs and openapi are disabled in production mode -> 404 even with token
            resp_docs = await client.get("/docs")
            assert resp_docs.status_code == 404

            resp_openapi = await client.get("/openapi.json")
            assert resp_openapi.status_code == 404

        # 6. Request with invalid token -> 401
        bad_headers = {"X-AKSA-Auth-Token": "completely-wrong-token"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=bad_headers) as client:
            resp_bad = await client.get("/api/v1/teams")
            assert resp_bad.status_code == 401
    finally:
        settings.dev_mode = orig_dev
        settings.auth_token = orig_token


def test_p0_engine_refuses_to_start_without_token_in_production() -> None:
    """Verify that launching app.main without an auth token in production mode immediately terminates."""
    proc = subprocess.run(
        [sys.executable, "-m", "app.main", "--production"],
        cwd="services/engine",
        capture_output=True,
        text=True,
        env={**dict(filter(lambda kv: kv[0] != "AKSA_AUTH_TOKEN" and kv[0] != "AKSA_DEV_MODE", dict().items()))},
    )
    assert proc.returncode == 1
    assert "FATAL" in proc.stderr
    assert "mode produksi" in proc.stderr
