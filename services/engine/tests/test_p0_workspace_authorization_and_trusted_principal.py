"""Tests for P0-02, P0-03, P0-04: Workspace Authorization, Trusted Principal, and HITL Fail-Closed."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.auth_context import get_default_host_principal, resolve_authenticated_principal
from app.core.sandbox import (
    RiskLevel,
    execution_policy_gateway,
    sandbox_manager,
)
from app.db.models import db_manager
from app.main import app


@pytest.fixture(autouse=True)
async def init_test_db():
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_workspace_listing_and_deletion_principal_isolation() -> None:
    """Verify Principal A cannot see or delete Principal B's workspaces (P0-02, P0-03)."""
    with tempfile.TemporaryDirectory() as dir_alice, tempfile.TemporaryDirectory() as dir_bob:
        # 1. Register workspace for Alice
        ws_alice = await db_manager.upsert_workspace({
            "id": f"ws_alice_{uuid.uuid4().hex[:8]}",
            "name": "Alice Workspace",
            "folder_path": dir_alice,
            "allow_read": True,
            "allow_write": True,
            "owner_id": "principal_alice",
        })

        # 2. Register workspace for Bob
        ws_bob = await db_manager.upsert_workspace({
            "id": f"ws_bob_{uuid.uuid4().hex[:8]}",
            "name": "Bob Workspace",
            "folder_path": dir_bob,
            "allow_read": True,
            "allow_write": True,
            "owner_id": "principal_bob",
        })

        transport = ASGITransport(app=app)
        auth_headers_alice = {
            "X-AKSA-Auth-Token": settings.auth_token,
            "X-Principal-ID": "principal_alice",
        }
        auth_headers_bob = {
            "X-AKSA-Auth-Token": settings.auth_token,
            "X-Principal-ID": "principal_bob",
        }

        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            # Alice lists workspaces -> sees Alice workspace, does NOT see Bob workspace
            res_list_alice = await client.get("/api/v1/workspaces", headers=auth_headers_alice)
            assert res_list_alice.status_code == 200
            alice_ids = [w["id"] for w in res_list_alice.json()["workspaces"]]
            assert ws_alice["id"] in alice_ids
            assert ws_bob["id"] not in alice_ids

            # Bob attempts to DELETE Alice's workspace -> 403 Forbidden
            res_del_bad = await client.delete(
                f"/api/v1/workspaces/{ws_alice['id']}",
                headers=auth_headers_bob,
            )
            assert res_del_bad.status_code == 403
            assert "Akses Ditolak" in res_del_bad.json()["detail"]

            # Alice DELETES own workspace -> 200 OK
            res_del_ok = await client.delete(
                f"/api/v1/workspaces/{ws_alice['id']}",
                headers=auth_headers_alice,
            )
            assert res_del_ok.status_code == 200
            assert res_del_ok.json()["deleted"] is True


@pytest.mark.asyncio
async def test_rag_search_workspace_authorization() -> None:
    """Verify /rag/search checks workspace existence, principal ownership, and allow_read (P0-02)."""
    with tempfile.TemporaryDirectory() as dir_alice, tempfile.TemporaryDirectory() as dir_charlie:
        ws_alice = await db_manager.upsert_workspace({
            "id": f"ws_alice_{uuid.uuid4().hex[:8]}",
            "name": "Alice Private Docs",
            "folder_path": dir_alice,
            "allow_read": True,
            "owner_id": "principal_alice",
        })

        ws_no_read = await db_manager.upsert_workspace({
            "id": f"ws_noread_{uuid.uuid4().hex[:8]}",
            "name": "No Read Allowed",
            "folder_path": dir_charlie,
            "allow_read": False,
            "owner_id": "principal_alice",
        })

        transport = ASGITransport(app=app)
        auth_headers_alice = {
            "X-AKSA-Auth-Token": settings.auth_token,
            "X-Principal-ID": "principal_alice",
        }
        auth_headers_bob = {
            "X-AKSA-Auth-Token": settings.auth_token,
            "X-Principal-ID": "principal_bob",
        }

        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            # 1. Empty workspace_id -> 400 Bad Request
            res_empty = await client.post(
                "/api/v1/rag/search",
                headers=auth_headers_alice,
                json={"query": "anggaran", "workspace_id": ""},
            )
            assert res_empty.status_code == 400

            # 2. Bob searches Alice's workspace -> 403 Forbidden
            res_cross = await client.post(
                "/api/v1/rag/search",
                headers=auth_headers_bob,
                json={"query": "anggaran", "workspace_id": ws_alice["id"]},
            )
            assert res_cross.status_code == 403
            assert "Akses Ditolak" in res_cross.json()["detail"]

            # 3. Alice searches workspace with allow_read=False -> 403 Forbidden
            res_no_read = await client.post(
                "/api/v1/rag/search",
                headers=auth_headers_alice,
                json={"query": "anggaran", "workspace_id": ws_no_read["id"]},
            )
            assert res_no_read.status_code == 403
            assert "allow_read" in res_no_read.json()["detail"]

            # 4. Alice searches own workspace with allow_read=True -> 200 OK
            res_ok = await client.post(
                "/api/v1/rag/search",
                headers=auth_headers_alice,
                json={"query": "anggaran", "workspace_id": ws_alice["id"]},
            )
            assert res_ok.status_code == 200
            assert "results" in res_ok.json()


@pytest.mark.asyncio
async def test_orchestrate_execute_workspace_authorization() -> None:
    """Verify /orchestrate/execute rejects un-whitelisted workspace paths and cross-principal access (P0-02)."""
    with tempfile.TemporaryDirectory() as dir_alice, tempfile.TemporaryDirectory() as dir_rogue:
        ws_alice = await db_manager.upsert_workspace({
            "id": f"ws_alice_{uuid.uuid4().hex[:8]}",
            "name": "Alice Workspace",
            "folder_path": dir_alice,
            "allow_read": True,
            "owner_id": "principal_alice",
        })

        transport = ASGITransport(app=app)
        auth_headers_alice = {
            "X-AKSA-Auth-Token": settings.auth_token,
            "X-Principal-ID": "principal_alice",
        }
        auth_headers_bob = {
            "X-AKSA-Auth-Token": settings.auth_token,
            "X-Principal-ID": "principal_bob",
        }

        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            # 1. Bob attempts to orchestrate in Alice's workspace -> 403 Forbidden
            res_cross = await client.post(
                "/api/v1/orchestrate/execute",
                headers=auth_headers_bob,
                json={"prompt": "list files", "workspace_id": ws_alice["id"]},
            )
            assert res_cross.status_code == 403

            # 2. Rogue arbitrary path outside authorized workspaces -> 403 Forbidden
            res_rogue = await client.post(
                "/api/v1/orchestrate/execute",
                headers=auth_headers_alice,
                json={"prompt": "list files", "workspace_path": dir_rogue},
            )
            assert res_rogue.status_code == 403


@pytest.mark.asyncio
async def test_principal_spoofing_rejected_in_production() -> None:
    """Verify that in production mode, caller cannot spoof X-Principal-ID (P0-03)."""
    orig_testing = settings.testing
    orig_dev = settings.dev_mode
    try:
        settings.testing = False
        settings.dev_mode = False

        transport = ASGITransport(app=app)
        auth_headers = {
            "X-AKSA-Auth-Token": settings.auth_token,
            "X-Principal-ID": "attacker_impersonating_admin",
        }
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            res = await client.get("/api/v1/workspaces", headers=auth_headers)
            assert res.status_code == 403
            assert "tidak sesuai dengan identitas host terautentikasi" in res.json()["detail"]
    finally:
        settings.testing = orig_testing
        settings.dev_mode = orig_dev


def test_hitl_grant_fails_closed_when_actual_action_id_is_missing() -> None:
    """Verify HITL grant cannot be consumed if actual action_id is missing or mismatched (P0-04)."""
    grant = execution_policy_gateway.create_grant(
        tool_name="filesystem.delete",
        arguments={"path": "/safe/test.txt"},
        action_id="act_critical_001",
        principal_id="principal_alice",
        resource_path="/safe/test.txt",
    )

    # 1. Missing action_id (None or empty) -> MUST fail-closed False!
    consumed_missing = execution_policy_gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="filesystem.delete",
        arguments={"path": "/safe/test.txt"},
        action_id=None,
        principal_id="principal_alice",
        resource_path="/safe/test.txt",
    )
    assert consumed_missing is False

    consumed_empty = execution_policy_gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="filesystem.delete",
        arguments={"path": "/safe/test.txt"},
        action_id="",
        principal_id="principal_alice",
        resource_path="/safe/test.txt",
    )
    assert consumed_empty is False

    # 2. Mismatched action_id -> MUST fail-closed False!
    consumed_mismatch = execution_policy_gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="filesystem.delete",
        arguments={"path": "/safe/test.txt"},
        action_id="act_spoofed_999",
        principal_id="principal_alice",
        resource_path="/safe/test.txt",
    )
    assert consumed_mismatch is False

    # 3. Exact matching action_id -> SUCCEEDS and consumes atomically!
    consumed_exact = execution_policy_gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="filesystem.delete",
        arguments={"path": "/safe/test.txt"},
        action_id="act_critical_001",
        principal_id="principal_alice",
        resource_path="/safe/test.txt",
    )
    assert consumed_exact is True

    # 4. Replay of consumed grant -> MUST be rejected!
    consumed_replay = execution_policy_gateway.verify_and_consume_grant(
        grant_id=grant.id,
        tool_name="filesystem.delete",
        arguments={"path": "/safe/test.txt"},
        action_id="act_critical_001",
        principal_id="principal_alice",
        resource_path="/safe/test.txt",
    )
    assert consumed_replay is False
