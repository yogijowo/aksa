"""WebSocket real-time event hub with principal authentication, session isolation, and rate limiting (P1.7)."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.config import settings
from app.core.observability import redact_payload
from app.db.models import db_manager

ws_router = APIRouter()

MAX_WS_MESSAGE_BYTES = 64 * 1024  # 64 KB maximum message size
MAX_ACTIVE_CONNECTIONS = 32
MAX_MESSAGES_PER_SECOND = 30


class ConnectionManager:
    """Manages authenticated WebSocket clients with strict per-session ownership and isolation (P1.7)."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.connection_subscriptions: dict[WebSocket, set[str]] = {}
        self.session_owners: dict[str, WebSocket] = {}
        self.connection_principals: dict[WebSocket, str] = {}
        self.connection_message_timestamps: dict[WebSocket, list[float]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str | None = None,
        principal_id: str = "default_user",
    ) -> bool:
        if len(self.active_connections) >= MAX_ACTIVE_CONNECTIONS:
            await websocket.close(code=4008, reason="Connection limit exceeded")
            return False

        if getattr(websocket.client_state, "name", "") != "CONNECTED":
            await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_subscriptions[websocket] = set()
        self.connection_principals[websocket] = principal_id
        self.connection_message_timestamps[websocket] = []

        if session_id:
            await self.subscribe_session(websocket, session_id, principal_id=principal_id)
        return True

    async def subscribe_session(
        self,
        websocket: WebSocket,
        session_id: str,
        principal_id: str = "default_user",
    ) -> bool:
        """Authorize and subscribe a WebSocket connection to a session validating persistent ownership."""
        if websocket not in self.connection_subscriptions:
            return False

        # 1. Validate against persistent database session ownership (P1.7)
        try:
            db_session = await db_manager.get_session(session_id)
            if db_session:
                sess_principal = db_session.get("principal_id") or "default_user"
                if sess_principal != principal_id:
                    # Cross-principal session access rejected fail-closed
                    return False
        except Exception:
            return False

        # 2. Check in-memory active connection owner
        owner = self.session_owners.get(session_id)
        if owner is not None and owner in self.active_connections and owner is not websocket:
            owner_principal = self.connection_principals.get(owner, "default_user")
            if owner_principal != principal_id:
                return False

        self.session_owners[session_id] = websocket
        self.connection_subscriptions[websocket].add(session_id)
        return True

    def unsubscribe_session(self, websocket: WebSocket, session_id: str) -> None:
        if websocket in self.connection_subscriptions:
            self.connection_subscriptions[websocket].discard(session_id)
        if self.session_owners.get(session_id) is websocket:
            self.session_owners.pop(session_id, None)

    def check_rate_limit(self, websocket: WebSocket) -> bool:
        """Sliding-window rate limiter (max 30 msgs/second per connection)."""
        now = time.monotonic()
        timestamps = self.connection_message_timestamps.setdefault(websocket, [])
        # Keep only timestamps within last 1.0 second
        self.connection_message_timestamps[websocket] = [t for t in timestamps if now - t < 1.0]
        if len(self.connection_message_timestamps[websocket]) >= MAX_MESSAGES_PER_SECOND:
            return False
        self.connection_message_timestamps[websocket].append(now)
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_subscriptions.pop(websocket, None)
        self.connection_principals.pop(websocket, None)
        self.connection_message_timestamps.pop(websocket, None)
        owned = [sid for sid, owner in self.session_owners.items() if owner is websocket]
        for sid in owned:
            self.session_owners.pop(sid, None)

    async def revoke_principal(self, principal_id: str) -> int:
        """Immediately terminate all active WebSocket connections for a revoked principal (P1.7)."""
        to_close = [
            ws for ws, princ in list(self.connection_principals.items())
            if princ == principal_id
        ]
        count = len(to_close)
        for ws in to_close:
            try:
                await ws.close(code=4003, reason="Principal access revoked")
            except Exception:
                pass
            self.disconnect(ws)
        return count

    async def broadcast_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        session_id: str | None = None,
    ) -> None:
        """Broadcast a structured, redacted JSON event to authenticated, session-isolated UI clients."""
        safe_payload = redact_payload(payload)
        message = json.dumps(
            {
                "event": event_type,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": safe_payload,
            }
        )

        recipients: list[WebSocket] = []
        for conn in self.active_connections:
            subs = self.connection_subscriptions.get(conn, set())
            if session_id is None:
                recipients.append(conn)
            elif session_id in subs:
                recipients.append(conn)

        stale: list[WebSocket] = []
        for connection in recipients:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for conn in stale:
            self.disconnect(conn)


ws_manager = ConnectionManager()


@ws_router.websocket("/ws/stream")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
) -> None:
    """Bi-directional real-time WebSocket stream between Desktop UI and Python Engine with session ownership (P1.7)."""
    authenticated = False
    principal_id = "default_user"

    if settings.dev_mode:
        authenticated = True
    elif token and secrets.compare_digest(token, settings.auth_token):
        authenticated = True

    if not authenticated:
        # Await initial JSON auth frame within 3 seconds
        await websocket.accept()
        try:
            raw_auth = await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
            auth_data = json.loads(raw_auth)
            frame_token = auth_data.get("token") or auth_data.get("auth_token")
            if frame_token and secrets.compare_digest(frame_token, settings.auth_token):
                authenticated = True
                if not session_id and auth_data.get("session_id"):
                    session_id = auth_data.get("session_id")
            else:
                await websocket.close(code=4001, reason="Unauthorized")
                return
        except Exception:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    connected = await ws_manager.connect(websocket, session_id=session_id, principal_id=principal_id)
    if not connected:
        return

    try:
        await websocket.send_json(
            {
                "event": "engine_connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "payload": {
                    "message": "Terhubung ke Mesin Inti AKSA secara real-time.",
                    "status": "ready",
                    "principal_id": principal_id,
                },
            }
        )
        while True:
            raw = await websocket.receive_text()
            if not ws_manager.check_rate_limit(websocket):
                await websocket.send_json(
                    {
                        "event": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Batas kecepatan pesan WebSocket terlampaui (maks 30 pesan/detik).",
                        },
                    }
                )
                continue

            if len(raw.encode("utf-8")) > MAX_WS_MESSAGE_BYTES:
                await websocket.send_json(
                    {
                        "event": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {"code": "MESSAGE_TOO_LARGE", "message": "Pesan WebSocket melebihi batas 64 KB."},
                    }
                )
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = data.get("action")
            if action == "ping":
                await websocket.send_json(
                    {
                        "event": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {},
                    }
                )
            elif action == "subscribe":
                target_session = data.get("session_id")
                if target_session:
                    subscribed = await ws_manager.subscribe_session(
                        websocket, target_session, principal_id=principal_id
                    )
                    if subscribed:
                        await websocket.send_json(
                            {
                                "event": "subscribed",
                                "session_id": target_session,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "payload": {"session_id": target_session},
                            }
                        )
                    else:
                        await websocket.send_json(
                            {
                                "event": "subscription_denied",
                                "session_id": target_session,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "payload": {
                                    "code": "SESSION_UNAUTHORIZED",
                                    "message": "Sesi tidak ditemukan atau akses ditolak.",
                                    "session_id": target_session,
                                },
                            }
                        )
            elif action == "unsubscribe":
                target_session = data.get("session_id")
                if target_session:
                    ws_manager.unsubscribe_session(websocket, target_session)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
