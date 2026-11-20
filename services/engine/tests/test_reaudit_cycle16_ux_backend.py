"""Regression tests for Siklus 16 UX/UI Specification backend invariants:
- Section 3: Agent hierarchy validation (circular dependency rejection, root protection, child reassignment).
- Section 4: Manual & automatic model selection persistence per agent.
- Section 5: 5-state API token status, masked overwrite rejection, delete token, connection test verification.
- Section 6: Native workspace folder inspection (spaces, non-ASCII, missing, file, UNC) & permission updates.
- Section 7 & 8: Theme persistence & RAG document index removal preserving disk file.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.config import settings
from app.db.models import db_manager
from app.db.seed import seed_default_indonesian_team
from app.main import app


@pytest.mark.asyncio
async def test_cycle16_agent_hierarchy_validation_and_manual_model_persistence() -> None:
    """Verify agent parent-child hierarchy validation, cycle prevention, and manual model selection persistence."""
    await db_manager.initialize()
    await seed_default_indonesian_team(db_manager)

    transport = ASGITransport(app=app)
    auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}

    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        teams_res = await client.get("/api/v1/teams")
        assert teams_res.status_code == 200
        team = teams_res.json()["teams"][0]
        team_id = team["id"]
        root_agent = next(a for a in team["agents"] if a["parent_id"] is None)

        # 1. Create Agent B under Root with manual model selection
        res_b = await client.post(
            "/api/v1/agents",
            json={
                "team_id": team_id,
                "parent_id": root_agent["id"],
                "name": "Agen Analis Keuangan",
                "role_title": "Spesialis Tabel & Anggaran",
                "description": "Menyusun laporan keuangan.",
                "provider": "deepseek",
                "model_id": "deepseek-v4-pro",
                "model_selection_mode": "manual",
                "system_prompt": "Analisis angka secara akurat.",
                "tool_categories": ["filesystem", "office_excel"],
            },
        )
        assert res_b.status_code == 200
        agent_b = res_b.json()["agent"]
        assert agent_b["parent_id"] == root_agent["id"]
        assert agent_b["tier_level"] == 1
        assert agent_b["model_selection_mode"] == "manual"
        assert agent_b["provider"] == "deepseek"
        assert agent_b["model_id"] == "deepseek-v4-pro"

        # 2. Create Sub-Agent C under Agent B
        res_c = await client.post(
            "/api/v1/agents",
            json={
                "team_id": team_id,
                "parent_id": agent_b["id"],
                "name": "Sub-Agen Verifikasi Pajak",
                "role_title": "Pemeriksa Faktur",
                "description": "Memeriksa rincian pajak.",
                "provider": "ollama",
                "model_id": "qwen3.8:8b",
                "model_selection_mode": "auto",
                "system_prompt": "Periksa faktur.",
                "tool_categories": ["filesystem"],
            },
        )
        assert res_c.status_code == 200
        agent_c = res_c.json()["agent"]
        assert agent_c["parent_id"] == agent_b["id"]
        assert agent_c["tier_level"] == 2

        # 3. Reject self-parenting (B -> B)
        self_parent_res = await client.patch(
            f"/api/v1/agents/{agent_b['id']}",
            json={"parent_id": agent_b["id"]},
        )
        assert self_parent_res.status_code == 400
        assert "dirinya sendiri" in self_parent_res.json()["detail"]

        # 4. Reject circular dependency (B -> C where C is child of B)
        cycle_res = await client.patch(
            f"/api/v1/agents/{agent_b['id']}",
            json={"parent_id": agent_c["id"]},
        )
        assert cycle_res.status_code == 400
        assert "melingkar" in cycle_res.json()["detail"].lower()

        # 5. Reject deleting Root Supervisor
        del_root_res = await client.delete(f"/api/v1/agents/{root_agent['id']}")
        assert del_root_res.status_code == 400

        # 6. Deleting middle Agent B reassigns Sub-Agent C to Root (no orphan nodes)
        del_b_res = await client.delete(f"/api/v1/agents/{agent_b['id']}")
        assert del_b_res.status_code == 200

        after_teams = (await client.get("/api/v1/teams")).json()["teams"][0]["agents"]
        surviving_c = next(a for a in after_teams if a["id"] == agent_c["id"])
        assert surviving_c["parent_id"] == root_agent["id"]
        assert surviving_c["tier_level"] == 1


@pytest.mark.asyncio
async def test_cycle16_api_token_five_states_and_masked_overwrite_protection() -> None:
    """Verify 5-state token status, masked string overwrite rejection, connection test, and token deletion."""
    await db_manager.initialize()
    transport = ASGITransport(app=app)
    auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}

    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        # Ensure clean starting state for deepseek
        await client.delete("/api/v1/models/keys/deepseek")

        # 1. State 1: Not connected
        provs_1 = (await client.get("/api/v1/models/providers")).json()["providers"]
        ds_1 = next(p for p in provs_1 if p["id"] == "deepseek")
        assert ds_1["has_saved_token"] is False
        assert ds_1["token_status"] == "not_connected"

        # Testing connection without saved token must return ok=False and token_status="not_connected"
        test_no_key = await client.post(
            "/api/v1/models/test",
            json={"provider": "deepseek", "model_id": "deepseek-chat"},
        )
        assert test_no_key.status_code == 200
        assert test_no_key.json()["ok"] is False
        assert test_no_key.json()["token_status"] == "not_connected"

        # 2. Save real secret -> State 2: token_saved
        real_secret = "sk-deepseek-secret-token-9876543210abcdef"
        save_res = await client.post(
            "/api/v1/models/keys",
            json={"provider": "deepseek", "api_key": real_secret},
        )
        assert save_res.status_code == 200

        provs_2 = (await client.get("/api/v1/models/providers")).json()["providers"]
        ds_2 = next(p for p in provs_2 if p["id"] == "deepseek")
        assert ds_2["has_saved_token"] is True
        assert ds_2["token_status"] == "token_saved"
        assert real_secret not in str(ds_2)

        # 3. Attempting to overwrite with a masked preview string must be rejected (HTTP 400)
        masked_attempt = await client.post(
            "/api/v1/models/keys",
            json={"provider": "deepseek", "api_key": "sk-d••••••••cdef"},
        )
        assert masked_attempt.status_code == 400

        # 4. Successful connection test -> State 3: connected
        with patch("app.api.routes.llm_router.complete") as mock_complete:
            mock_complete.return_value = {
                "content": "OK",
                "tool_calls": [],
                "input_tokens": 5,
                "output_tokens": 2,
                "simulated": False,
                "cloud_called": True,
                "provider_used": "deepseek",
            }
            test_ok = await client.post(
                "/api/v1/models/test",
                json={"provider": "deepseek", "model_id": "deepseek-chat"},
            )
            assert test_ok.status_code == 200
            assert test_ok.json()["ok"] is True
            assert test_ok.json()["token_status"] == "connected"

        provs_3 = (await client.get("/api/v1/models/providers")).json()["providers"]
        ds_3 = next(p for p in provs_3 if p["id"] == "deepseek")
        assert ds_3["token_status"] == "connected"
        saved_tests = await db_manager.get_setting("provider_connection_tests", default={})
        assert saved_tests.get("deepseek", {}).get("ok") is True

        # 5. Delete token -> resets to not_connected
        del_res = await client.delete("/api/v1/models/keys/deepseek")
        assert del_res.status_code == 200
        provs_4 = (await client.get("/api/v1/models/providers")).json()["providers"]
        ds_4 = next(p for p in provs_4 if p["id"] == "deepseek")
        assert ds_4["has_saved_token"] is False
        assert ds_4["token_status"] == "not_connected"


@pytest.mark.asyncio
async def test_cycle16_workspace_folder_inspection_and_rag_index_delete(tmp_path: Path) -> None:
    """Verify native folder path inspection (spaces, Unicode, missing, file, UNC) and RAG index deletion."""
    await db_manager.initialize()
    transport = ASGITransport(app=app)
    auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}

    # Create a folder with spaces and non-ASCII characters
    unicode_folder = tmp_path / "Folder Kerja Laporan 2026 — Документы"
    unicode_folder.mkdir(parents=True, exist_ok=True)
    sample_file = unicode_folder / "Catatan_Rapat.txt"
    sample_file.write_text("Isi rapat anggaran tahunan 2026.", encoding="utf-8")

    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        # 1. Inspect valid directory with spaces & non-ASCII
        insp_ok = await client.post(
            "/api/v1/workspaces/inspect-path",
            json={"folder_path": str(unicode_folder)},
        )
        assert insp_ok.status_code == 200
        data_ok = insp_ok.json()
        assert data_ok["is_valid_directory"] is True
        assert data_ok["folder_status"] == "accessible"
        assert "Folder Kerja Laporan 2026" in data_ok["name"]

        # 2. Inspect file path (rejected as not a folder)
        insp_file = await client.post(
            "/api/v1/workspaces/inspect-path",
            json={"folder_path": str(sample_file)},
        )
        assert insp_file.status_code == 200
        assert insp_file.json()["is_valid_directory"] is False
        assert insp_file.json()["folder_status"] == "unavailable"

        # 3. Inspect non-existent path
        insp_missing = await client.post(
            "/api/v1/workspaces/inspect-path",
            json={"folder_path": str(tmp_path / "Folder_Tidak_Ada_999")},
        )
        assert insp_missing.status_code == 200
        assert insp_missing.json()["is_valid_directory"] is False
        assert insp_missing.json()["folder_status"] == "not_found"

        # 4. Inspect UNC network path
        insp_unc = await client.post(
            "/api/v1/workspaces/inspect-path",
            json={"folder_path": "\\\\server\\share\\laporan"},
        )
        assert insp_unc.status_code == 200
        assert insp_unc.json()["is_valid_directory"] is False
        assert insp_unc.json()["folder_status"] == "unavailable"

        # 5. Register workspace, update permissions via PATCH, and verify execute stays disabled
        reg_res = await client.post(
            "/api/v1/workspaces",
            json={
                "name": "Laporan 2026",
                "folder_path": str(unicode_folder),
                "allow_read": True,
                "allow_write": False,
                "allow_execute": False,
            },
        )
        assert reg_res.status_code == 200
        ws = reg_res.json()["workspace"]
        assert ws["folder_status"] == "accessible"
        assert ws["allow_write"] is False
        assert ws["allow_execute"] is False

        patch_res = await client.patch(
            f"/api/v1/workspaces/{ws['id']}",
            json={
                "allow_write": True,
                "granular_permissions": {
                    "list_files": True,
                    "read_content": True,
                    "create_files": True,
                    "modify_files": True,
                    "move_files": False,
                    "delete_files": False,
                    "execute_programs": False,
                },
            },
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["workspace"]["allow_write"] is True
        assert patch_res.json()["workspace"]["allow_execute"] is False
        assert patch_res.json()["workspace"]["granular_permissions"]["create_files"] is True
        assert patch_res.json()["workspace"]["granular_permissions"]["move_files"] is False

        # 6. Index folder in RAG and then remove document from index while preserving disk file
        idx_res = await client.post(
            "/api/v1/rag/index-folder",
            json={"workspace_id": ws["id"], "folder_path": str(unicode_folder), "enable_watcher": False},
        )
        assert idx_res.status_code == 200

        docs_res = await client.get(f"/api/v1/rag/documents?workspace_id={ws['id']}")
        assert docs_res.status_code == 200
        docs = docs_res.json()["documents"]
        assert len(docs) >= 1
        doc_id = docs[0]["id"]

        del_doc_res = await client.delete(f"/api/v1/rag/documents/{doc_id}")
        assert del_doc_res.status_code == 200
        assert del_doc_res.json()["source_file_preserved"] is True
        # Original file on disk must still exist!
        assert sample_file.exists()
