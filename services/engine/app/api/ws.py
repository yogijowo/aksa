"""WebSocket real-time event hub for streaming agent steps, tokens, and HITL approvals."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.config import settings

ws_router = APIRouter()


class ConnectionManager:
    """Manages authenticated WebSocket clients with per-session isolation."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.connection_subscriptions: dict[WebSocket, set[str]] = {}

    async def connect(self, websocket: WebSocket, session_id: str | None = None) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_subscriptions[websocket] = set()
        if session_id:
            self.connection_subscriptions[websocket].add(session_id)

    def subscribe_session(self, websocket: WebSocket, session_id: str) -> None:
        if websocket in self.connection_subscriptions:
            self.connection_subscriptions[websocket].add(session_id)

    def unsubscribe_session(self, websocket: WebSocket, session_id: str) -> None:
        if websocket in self.connection_subscriptions:
            self.connection_subscriptions[websocket].discard(session_id)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_subscriptions.pop(websocket, None)

    async def broadcast_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        session_id: str | None = None,
    ) -> None:
        """Broadcast a structured JSON event to authenticated, session-isolated UI clients."""
        message = json.dumps(
            {
                "event": event_type,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
        )

        recipients: list[WebSocket] = []
        for conn in self.active_connections:
            subs = self.connection_subscriptions.get(conn, set())
            if session_id is None:
                # Global event - send to all
                recipients.append(conn)
            elif session_id in subs:
                # Targeted session event: deliver strictly to explicit subscribers
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
    """Bi-directional real-time WebSocket stream between Desktop UI and Python Engine with session isolation."""
    if not settings.dev_mode and token != settings.auth_token:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await ws_manager.connect(websocket, session_id=session_id)
    try:
        await websocket.send_json(
            {
                "event": "engine_connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "payload": {
                    "message": "Terhubung ke Mesin Inti AKSA secara real-time.",
                    "status": "ready",
                },
            }
        )
        while True:
            raw = await websocket.receive_text()
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
                    ws_manager.subscribe_session(websocket, target_session)
                    await websocket.send_json(
                        {
                            "event": "subscribed",
                            "session_id": target_session,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "payload": {"session_id": target_session},
                        }
                    )
            elif action == "unsubscribe":
                target_session = data.get("session_id")
                if target_session:
                    ws_manager.unsubscribe_session(websocket, target_session)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

