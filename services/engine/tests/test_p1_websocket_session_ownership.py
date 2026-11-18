"""Tests for P1.7: WebSocket Session Ownership, Persistent Principal Authorization, and Rate Limiting."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.api.ws import ConnectionManager, MAX_WS_MESSAGE_BYTES, MAX_MESSAGES_PER_SECOND
from app.db.models import db_manager


@pytest.fixture(autouse=True)
async def init_db():
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_session_ownership_cross_principal_denied():
    """Verify principal A cannot subscribe to or intercept a session owned by principal B (P1.7)."""
    session_id = f"sess_bob_{uuid.uuid4().hex[:12]}"
    # 1. Create a session owned by principal_bob
    bob_session = await db_manager.create_session({
        "id": session_id,
        "title": "Bob Confidential Session",
        "principal_id": "principal_bob",
    })

    manager = ConnectionManager()
    alice_ws = MagicMock()
    alice_ws.client_state.name = "CONNECTED"

    # Alice connects with principal_id = "principal_alice"
    await manager.connect(alice_ws, principal_id="principal_alice")

    # Alice attempts to subscribe to Bob's session -> must be denied fail-closed
    subscribed = await manager.subscribe_session(alice_ws, session_id, principal_id="principal_alice")
    assert subscribed is False
    assert session_id not in manager.connection_subscriptions[alice_ws]

    # Bob connects with principal_id = "principal_bob" -> must be allowed
    bob_ws = MagicMock()
    bob_ws.client_state.name = "CONNECTED"
    await manager.connect(bob_ws, principal_id="principal_bob")

    bob_subscribed = await manager.subscribe_session(bob_ws, session_id, principal_id="principal_bob")
    assert bob_subscribed is True
    assert session_id in manager.connection_subscriptions[bob_ws]


@pytest.mark.asyncio
async def test_websocket_rate_limiter():
    """Verify that sending more than MAX_MESSAGES_PER_SECOND is detected and rate limited."""
    manager = ConnectionManager()
    ws = MagicMock()
    ws.client_state.name = "CONNECTED"
    await manager.connect(ws)

    # Send up to limit -> all OK
    for _ in range(MAX_MESSAGES_PER_SECOND):
        assert manager.check_rate_limit(ws) is True

    # 31st message within same second -> rate limited
    assert manager.check_rate_limit(ws) is False


@pytest.mark.asyncio
async def test_principal_revocation_terminates_connections():
    """Verify revoking a principal terminates all their active WebSocket connections."""
    manager = ConnectionManager()

    ws1 = MagicMock()
    ws1.client_state.name = "CONNECTED"
    ws1.close = AsyncMock()

    ws2 = MagicMock()
    ws2.client_state.name = "CONNECTED"
    ws2.close = AsyncMock()

    await manager.connect(ws1, principal_id="revoked_user")
    await manager.connect(ws2, principal_id="active_user")

    assert len(manager.active_connections) == 2

    # Revoke revoked_user
    closed_count = await manager.revoke_principal("revoked_user")
    assert closed_count == 1
    ws1.close.assert_called_once_with(code=4003, reason="Principal access revoked")
    assert ws1 not in manager.active_connections
    assert ws2 in manager.active_connections
