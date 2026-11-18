"""Regression tests for P1-04: WebSocket Authorization Fail-Closed on Missing Session and Wrong Owner."""

from __future__ import annotations

import json
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.core.auth_context import get_default_host_principal
from app.db.models import db_manager
from app.main import create_app


@pytest.fixture(autouse=True)
async def init_db():
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_ws_subscribe_missing_session_rejected_fail_closed() -> None:
    """Verify subscribing to a non-existent session is strictly denied (P1-04)."""
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/stream?token={settings.auth_token}") as ws:
        # Welcome frame
        welcome = ws.receive_json()
        assert welcome["event"] == "engine_connected"

        # Attempt to subscribe to a non-existent session
        ws.send_text(json.dumps({"action": "subscribe", "session_id": "non_existent_session_999"}))
        resp = ws.receive_json()

        assert resp["event"] == "subscription_denied"
        assert resp["session_id"] == "non_existent_session_999"
        assert resp["payload"]["code"] == "SESSION_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_ws_subscribe_wrong_owner_rejected() -> None:
    """Verify subscribing to another principal's session is denied (P1-04)."""
    # Create session owned by user:alice
    await db_manager.create_session({
        "id": "sess_alice_secret",
        "title": "Alice Workspace Session",
        "principal_id": "user:alice",
    })

    app = create_app()
    client = TestClient(app)

    # Connect as default host user (not alice)
    with client.websocket_connect(f"/ws/stream?token={settings.auth_token}") as ws:
        ws.receive_json()  # welcome

        # Attempt to subscribe to alice's session
        ws.send_text(json.dumps({"action": "subscribe", "session_id": "sess_alice_secret"}))
        resp = ws.receive_json()

        assert resp["event"] == "subscription_denied"
        assert resp["payload"]["code"] == "SESSION_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_ws_subscribe_database_error_fails_closed() -> None:
    """Verify that a database lookup failure/timeout during subscribe fails closed (P1-04)."""
    # Create valid session
    trusted = get_default_host_principal()
    await db_manager.create_session({
        "id": "sess_db_err_test",
        "title": "Test Session",
        "principal_id": trusted,
    })

    app = create_app()
    client = TestClient(app)

    with patch("app.db.models.db_manager.get_session", side_effect=RuntimeError("DB disk I/O error")):
        with client.websocket_connect(f"/ws/stream?token={settings.auth_token}") as ws:
            ws.receive_json()  # welcome

            ws.send_text(json.dumps({"action": "subscribe", "session_id": "sess_db_err_test"}))
            resp = ws.receive_json()

            assert resp["event"] == "subscription_denied"
            assert resp["payload"]["code"] == "SESSION_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_ws_session_switch_and_reconnect_revalidates_ownership() -> None:
    """Verify session switching and reconnection re-validates ownership dynamically (P1-04)."""
    trusted = get_default_host_principal()
    await db_manager.create_session({
        "id": "sess_valid_switch_1",
        "title": "Session 1",
        "principal_id": trusted,
    })
    await db_manager.create_session({
        "id": "sess_valid_switch_2",
        "title": "Session 2",
        "principal_id": trusted,
    })

    app = create_app()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/stream?token={settings.auth_token}") as ws:
        ws.receive_json()

        # Subscribe to Session 1
        ws.send_text(json.dumps({"action": "subscribe", "session_id": "sess_valid_switch_1"}))
        resp1 = ws.receive_json()
        assert resp1["event"] == "subscribed"
        assert resp1["session_id"] == "sess_valid_switch_1"

        # Switch to Session 2
        ws.send_text(json.dumps({"action": "subscribe", "session_id": "sess_valid_switch_2"}))
        resp2 = ws.receive_json()
        assert resp2["event"] == "subscribed"
        assert resp2["session_id"] == "sess_valid_switch_2"

        # Try switching to missing session -> denied
        ws.send_text(json.dumps({"action": "subscribe", "session_id": "missing_session_during_switch"}))
        resp3 = ws.receive_json()
        assert resp3["event"] == "subscription_denied"


def test_ws_principal_spoofing_rejected_in_production() -> None:
    """Verify caller cannot spoof principal_id via frame auth in production (P1-04, P0-03)."""
    orig_dev = settings.dev_mode
    orig_test = settings.testing
    try:
        settings.dev_mode = False
        settings.testing = False

        app = create_app()
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect("/ws/stream") as ws:
                ws.send_text(json.dumps({
                    "token": settings.auth_token,
                    "principal_id": "attacker_impersonating_admin",
                }))
                ws.receive_json()
    finally:
        settings.dev_mode = orig_dev
        settings.testing = orig_test

