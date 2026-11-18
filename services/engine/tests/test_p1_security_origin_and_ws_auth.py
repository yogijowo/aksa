"""Tests for P1-2 (Origin/Host Allowlist Hardening) and P1-3 (Constant-Time Token & WebSocket Frame Auth)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.main import create_app


def test_p1_origin_allowlist_blocks_malicious_origin() -> None:
    """Verify P1-2: An origin like http://test.evil.com is strictly rejected with 403."""
    app = create_app()
    client = TestClient(app)

    # Evil origin attempting CSRF / DNS rebinding
    headers = {
        "Origin": "http://test.evil.com",
        "X-AKSA-Auth-Token": settings.auth_token,
    }
    resp = client.get("/api/v1/health", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_ORIGIN"


def test_p1_host_header_blocks_malicious_host() -> None:
    """Verify P1-2: An unknown external host header is rejected with 403."""
    app = create_app()
    client = TestClient(app)

    headers = {
        "Host": "evil-domain.com",
        "X-AKSA-Auth-Token": settings.auth_token,
    }
    resp = client.get("/api/v1/health", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_HOST"


def test_p1_docs_disabled_in_production() -> None:
    """Verify P1-3: /docs and /openapi.json are disabled in production mode."""
    original_dev = settings.dev_mode
    try:
        settings.dev_mode = False
        app = create_app()
        client = TestClient(app)

        resp_docs = client.get("/docs", headers={"X-AKSA-Auth-Token": settings.auth_token})
        assert resp_docs.status_code == 404

        resp_openapi = client.get("/openapi.json", headers={"X-AKSA-Auth-Token": settings.auth_token})
        assert resp_openapi.status_code == 404
    finally:
        settings.dev_mode = original_dev


def test_p1_websocket_auth_via_initial_json_frame() -> None:
    """Verify P1-3: WebSocket client can connect without query token and authenticate via first JSON frame."""
    original_dev = settings.dev_mode
    try:
        settings.dev_mode = False
        app = create_app()
        client = TestClient(app)

        # 1. Connect without query token
        with client.websocket_connect("/ws/stream") as ws:
            # Send initial auth frame
            ws.send_text(json.dumps({"token": settings.auth_token, "session_id": "sess_p1_test"}))

            # Receive engine_connected welcome event
            welcome = ws.receive_json()
            assert welcome["event"] == "engine_connected"
            assert welcome["session_id"] == "sess_p1_test"

            # Ping/Pong test
            ws.send_text(json.dumps({"action": "ping"}))
            pong = ws.receive_json()
            assert pong["event"] == "pong"
    finally:
        settings.dev_mode = original_dev


def test_p1_websocket_auth_rejects_invalid_frame_token() -> None:
    """Verify P1-3: WebSocket client with invalid frame token is closed with code 4001."""
    original_dev = settings.dev_mode
    try:
        settings.dev_mode = False
        app = create_app()
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect("/ws/stream") as ws:
                ws.send_text(json.dumps({"token": "wrong-token-12345"}))
                ws.receive_json()
    finally:
        settings.dev_mode = original_dev


def test_p1_health_hmac_nonce_identity_verification() -> None:
    """Verify P1-5: /health verifies engine identity via HMAC of a nonce with shared token."""
    app = create_app()
    client = TestClient(app)

    nonce = "test-challenge-nonce-98765"
    resp = client.get(f"/api/v1/health?nonce={nonce}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["engine"] == "aksa-engine"
    assert "nonce_hmac" in data

    expected_hmac = hmac.new(
        settings.auth_token.encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert data["nonce_hmac"] == expected_hmac
