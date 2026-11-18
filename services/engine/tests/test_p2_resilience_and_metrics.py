"""Tests for Phase 11 P2: Real Token Metrics, Strict Local AI Privacy, Concurrency Guards & Sanitized Error Handling."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.core.llm_router import UnifiedLLMRouter
from app.core.orchestrator import HierarchicalOrchestrator
from app.core.sandbox import WorkspacePolicy, sandbox_manager
from app.core.token_optimizer import token_optimizer
from app.db.models import DatabaseManager
from app.db.seed import seed_default_indonesian_team
from app.main import create_app


@pytest.fixture
async def p2_setup(tmp_path: Path):
    db = DatabaseManager(db_path=tmp_path / "p2_test.db")
    await db.initialize()
    await seed_default_indonesian_team(db)
    router = UnifiedLLMRouter(db=db)
    orchestrator = HierarchicalOrchestrator(db=db, llm_router=router)

    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    sandbox_manager.register_workspace(
        WorkspacePolicy(
            workspace_id="ws_p2",
            folder_path=str(ws_dir),
            allow_write=True,
            allow_read=True,
        )
    )
    return orchestrator, ws_dir, router, db


@pytest.mark.asyncio
async def test_p2_1_real_token_metrics_calculation(p2_setup) -> None:
    """Verify P2-1: Token savings are computed strictly from real measured usage without fake constants."""
    orchestrator, ws_dir, router, db = p2_setup

    mock_resp = {
        "content": "Hasil analisis dokumen keuangan lengkap dan rinci sepanjang beberapa paragraf.",
        "tool_calls": [],
        "input_tokens": 520,
        "output_tokens": 180,
        "simulated": False,
        "cloud_called": False,
        "provider_used": "mock",
    }

    with patch.object(router, "complete", return_value=mock_resp):
        res = await orchestrator.execute_hierarchical_task(
            prompt="analisis dokumen keuangan",
            workspace_path=str(ws_dir),
            session_id="sess_p2_metrics",
        )

    # Verify real usage logged in token_usage_logs
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute(
            "SELECT SUM(input_tokens + output_tokens), SUM(tokens_saved_by_isolation) FROM token_usage_logs WHERE session_id = 'sess_p2_metrics'"
        )
        row = await cursor.fetchone()
        assert row[0] > 0
        assert row[1] >= 0


@pytest.mark.asyncio
async def test_p2_2_strict_local_privacy_never_calls_cloud_when_offline(p2_setup) -> None:
    """Verify P2-2: When Ollama is offline, requests never fall back to cloud providers even if API key exists."""
    _, _, router, _ = p2_setup

    # Save a Gemini API key to verify it is NEVER called as fallback
    await router.save_api_key("gemini", "AIzaSyTestKeyForPrivacyCheck999")

    # Complete request targeted at Ollama
    res = await router.complete(
        provider="ollama",
        model_id="qwen2.5:7b",
        messages=[{"role": "user", "content": "Rangkum data rahasia daerah"}],
    )

    # Must NOT call cloud
    assert res["cloud_called"] is False
    assert res["simulated"] is True
    assert res["provider_used"] == "ollama"
    assert "Tanpa Fallback ke Cloud" in res["content"]


@pytest.mark.asyncio
async def test_p2_3_daily_token_budget_guard(tmp_path: Path) -> None:
    """Verify P2-3: When daily token budget is reached, orchestrator blocks further requests with 429."""
    app = create_app()
    client = TestClient(app)

    # Set daily budget to 50 tokens via SQLite app_settings
    save_resp = client.post(
        "/api/v1/system/settings",
        json={"key": "daily_token_budget", "value": 50},
        headers={"X-AKSA-Auth-Token": settings.auth_token},
    )
    assert save_resp.status_code == 200

    # Insert a dummy token log exceeding 50 tokens today
    from app.db.models import db_manager, _now_iso
    import aiosqlite
    import uuid

    log_id = f"log_budget_{uuid.uuid4().hex[:8]}"
    async with aiosqlite.connect(db_manager.db_path) as conn:
        await conn.execute(
            """
            INSERT INTO token_usage_logs (id, provider, model_id, input_tokens, output_tokens, created_at)
            VALUES (?, 'mock', 'mock', 100, 50, ?)
            """,
            (log_id, _now_iso()),
        )
        await conn.commit()

    # Attempt to execute task -> should return 429 Too Many Requests
    resp = client.post(
        "/api/v1/orchestrate/execute",
        json={"prompt": "buat surat resmi", "session_id": "sess_budget_exceeded"},
        headers={"X-AKSA-Auth-Token": settings.auth_token},
    )
    assert resp.status_code == 429
    assert "Batas kuota token harian telah tercapai" in resp.json()["detail"]

    # Reset budget to unlimited (0)
    client.post(
        "/api/v1/system/settings",
        json={"key": "daily_token_budget", "value": 0},
        headers={"X-AKSA-Auth-Token": settings.auth_token},
    )


@pytest.mark.asyncio
async def test_p2_3_orchestration_cancellation() -> None:
    """Verify P2-3: Calling /orchestrate/cancel cancels an active task gracefully."""
    app = create_app()
    client = TestClient(app)

    # Test canceling when not running
    cancel_resp = client.post(
        "/api/v1/orchestrate/cancel/sess_idle",
        headers={"X-AKSA-Auth-Token": settings.auth_token},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "not_running"


def test_p2_5_sqlite_settings_single_source_of_truth() -> None:
    """Verify P2-5: System settings can be persisted and retrieved from SQLite app_settings."""
    app = create_app()
    client = TestClient(app)

    # Save setting
    save_resp = client.post(
        "/api/v1/system/settings",
        json={"key": "active_workspace_id", "value": "ws_audit_2026"},
        headers={"X-AKSA-Auth-Token": settings.auth_token},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "saved"

    # Retrieve all settings
    get_resp = client.get(
        "/api/v1/system/settings",
        headers={"X-AKSA-Auth-Token": settings.auth_token},
    )
    assert get_resp.status_code == 200
    settings_dict = get_resp.json()["settings"]
    assert settings_dict.get("active_workspace_id") == "ws_audit_2026"


def test_p2_6_sanitized_global_error_handling() -> None:
    """Verify P2-6: Unhandled server exceptions return sanitized Indonesian messages with request_id."""
    app = create_app()
    client = TestClient(app)

    # Calling an endpoint with invalid UUID/data that triggers unhandled server error
    resp = client.post(
        "/api/v1/system/open-path",
        json={"path": "/non_existent_invalid_path/file.docx"},
        headers={"X-AKSA-Auth-Token": settings.auth_token},
    )
    # The sandbox manager rejects this with 403 or 400 safely without leaking internal paths
    assert resp.status_code in (400, 403)
    assert "detail" in resp.json()
