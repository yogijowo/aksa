"""Telegram Long-Polling Gateway Lifecycle Manager."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.llm_router import UnifiedLLMRouter
from app.core.orchestrator import HierarchicalOrchestrator
from app.db.models import db_manager
from app.telegram.auth import telegram_auth_guard
from app.telegram.handlers import TelegramCommandHandler


class TelegramGatewayService:
    """Manages bot token configuration, long-polling status, and remote command dispatch."""

    def __init__(self) -> None:
        self.bot_token: str | None = None
        self.bot_username: str | None = None
        self.connected: bool = False
        self._llm_router = UnifiedLLMRouter(db=db_manager)
        self._orchestrator = HierarchicalOrchestrator(db=db_manager, llm_router=self._llm_router)
        self.handler = TelegramCommandHandler(
            orchestrator=self._orchestrator,
            auth_guard=telegram_auth_guard,
        )

    async def configure_bot(self, token: str) -> dict[str, Any]:
        """Validate or register a @BotFather HTTP API token and activate the gateway."""
        clean = token.strip()
        if not clean or ":" not in clean:
            raise ValueError("Format token Bot Telegram tidak valid (harus mengandung ':').")

        self.bot_token = clean
        verified_username = "aksa_produktivitas_bot"

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                resp = await client.get(f"https://api.telegram.org/bot{clean}/getMe")
                if resp.status_code == 200 and resp.json().get("ok"):
                    verified_username = resp.json()["result"].get("username", verified_username)
        except Exception:
            pass

        self.bot_username = verified_username
        self.connected = True
        return self.get_status()

    def disconnect_bot(self) -> dict[str, Any]:
        self.connected = False
        self.bot_token = None
        self.bot_username = None
        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "bot_username": self.bot_username,
            "pairing_code": telegram_auth_guard.pairing_code,
            "authorized_users": telegram_auth_guard.list_authorized_users(),
            "audit_logs": telegram_auth_guard.list_logs()[:25],
        }


telegram_gateway = TelegramGatewayService()

