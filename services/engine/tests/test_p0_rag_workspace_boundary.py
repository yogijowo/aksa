"""Regression tests for Prompt 2 (P0.1): RAG workspace boundary authorization and path jail enforcement."""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.sandbox import SandboxViolationError, canonicalize_and_validate_path
from app.db.models import DatabaseManager
from app.main import create_app
from app.rag.store import HybridRAGStore


@pytest.mark.asyncio
async def test_p0_rag_traversal_and_encoded_traversal_rejected(tmp_path: Path) -> None:
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("SUPER_SECRET_PAYLOAD", encoding="utf-8")

    db = DatabaseManager(db_path=tmp_path / "test.db")
    await db.initialize()
    await db.upsert_workspace({
        "id": "ws_test_boundary",
        "name": "Workspace Boundary Test",
        "folder_path": str(ws_dir),
        "allow_read": True,
        "owner_id": "user_owner",
    })
    store = HybridRAGStore(db=db, vector_dir=tmp_path / "vectors")

    # 1. Plain traversal ../
    with pytest.raises(SandboxViolationError):
        canonicalize_and_validate_path("../outside/secret.txt", ws_dir)

    with pytest.raises(SandboxViolationError):
        await store.index_file("ws_test_boundary", ws_dir / ".." / "outside" / "secret.txt", principal_id="user_owner")

    # 2. URL-encoded traversal (%2e%2e%2f)
    with pytest.raises(SandboxViolationError):
        canonicalize_and_validate_path("%2e%2e%2foutside%2fsecret.txt", ws_dir)

    # 3. Double-encoded traversal (%252e%252e%252f)
    with pytest.raises(SandboxViolationError):
        canonicalize_and_validate_path("%252e%252e%252foutside%252fsecret.txt", ws_dir)

    # 4. Traversal with Windows slashes
    with pytest.raises(SandboxViolationError):
        canonicalize_and_validate_path("..\\outside\\secret.txt", ws_dir)


@pytest.mark.asyncio
async def test_p0_rag_absolute_path_outside_root_rejected(tmp_path: Path) -> None:
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    outside_file = tmp_path / "private_outside.txt"
    outside_file.write_text("PRIVATE_DATA", encoding="utf-8")

    db = DatabaseManager(db_path=tmp_path / "test.db")
    await db.initialize()
    await db.upsert_workspace({
        "id": "ws_abs_test",
        "name": "Abs Path Test",
        "folder_path": str(ws_dir),
        "owner_id": "user_owner",
    })
    store = HybridRAGStore(db=db, vector_dir=tmp_path / "vectors")

    with pytest.raises(SandboxViolationError):
        canonicalize_and_validate_path(str(outside_file), ws_dir)

    with pytest.raises(SandboxViolationError):
        await store.index_file("ws_abs_test", outside_file, principal_id="user_owner")


@pytest.mark.asyncio
async def test_p0_rag_symlink_escape_and_nested_symlink_rejected(tmp_path: Path) -> None:
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    outside_dir = tmp_path / "outside_secure"
    outside_dir.mkdir()

    outside_file = outside_dir / "confidential.txt"
    outside_file.write_text("CONFIDENTIAL_TOP_SECRET", encoding="utf-8")

    # Valid internal document
    valid_file = ws_dir / "valid_doc.txt"
    valid_file.write_text("Dokumen resmi internal yang sah.", encoding="utf-8")

    # 1. Symlink escape inside workspace pointing outside
    symlink_file = ws_dir / "symlink_escape.txt"
    try:
        symlink_file.symlink_to(outside_file)
    except OSError:
        pytest.skip("Symlinks not supported on this platform/privilege level")

    # 2. Nested symlink: link1 -> link2 -> outside_file
    nested_dir = ws_dir / "nested"
    nested_dir.mkdir()
    link2 = nested_dir / "link2.txt"
    link2.symlink_to(outside_file)
    link1 = nested_dir / "link1.txt"
    link1.symlink_to(link2)

    # 3. Directory symlink pointing outside
    dir_symlink = ws_dir / "dir_escape"
    dir_symlink.symlink_to(outside_dir)

    db = DatabaseManager(db_path=tmp_path / "test.db")
    await db.initialize()
    await db.upsert_workspace({
        "id": "ws_symlink_test",
        "name": "Symlink Test",
        "folder_path": str(ws_dir),
        "owner_id": "user_owner",
    })
    store = HybridRAGStore(db=db, vector_dir=tmp_path / "vectors")

    # Test direct file indexing rejects symlinks pointing outside
    with pytest.raises(SandboxViolationError):
        await store.index_file("ws_symlink_test", symlink_file, principal_id="user_owner")

    with pytest.raises(SandboxViolationError):
        await store.index_file("ws_symlink_test", link1, principal_id="user_owner")

    # Test folder indexing: only valid_doc.txt must be indexed; symlinks and directory escapes must be SKIPPED!
    stats = await store.index_workspace_folder("ws_symlink_test", principal_id="user_owner")
    assert stats["indexed"] == 1
    assert stats["total_files"] == 1

    # Verify search does NOT leak confidential data
    search_res = await store.hybrid_search("CONFIDENTIAL", workspace_id="ws_symlink_test")
    assert not any("confidential" in r.get("content", "").lower() for r in search_res)
    assert not any("confidential" in r.get("file_name", "").lower() for r in search_res)

    # Search for internal content succeeds
    valid_search = await store.hybrid_search("resmi internal", workspace_id="ws_symlink_test")
    assert len(valid_search) > 0
    assert "resmi internal" in valid_search[0]["content"]


@pytest.mark.asyncio
async def test_p0_rag_different_principal_rejected(tmp_path: Path) -> None:
    ws_dir = tmp_path / "workspace_alice"
    ws_dir.mkdir()
    doc = ws_dir / "alice_doc.txt"
    doc.write_text("Data rahasia milik Alice.", encoding="utf-8")

    db = DatabaseManager(db_path=tmp_path / "test.db")
    await db.initialize()
    await db.upsert_workspace({
        "id": "ws_alice",
        "name": "Workspace Alice",
        "folder_path": str(ws_dir),
        "owner_id": "alice_id",
        "allow_read": True,
    })
    store = HybridRAGStore(db=db, vector_dir=tmp_path / "vectors")

    # Calling as bob must raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        await store.index_workspace_folder("ws_alice", principal_id="bob_id")
    assert "Principal tidak memiliki izin" in str(exc_info.value)

    # Calling index_file as bob must raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        await store.index_file("ws_alice", doc, principal_id="bob_id")
    assert "Principal tidak memiliki izin" in str(exc_info.value)

    # Verify audit event logged for principal mismatch
    audits = await db.list_permission_audit_events(limit=10)
    assert any(a["reason_code"] == "PRINCIPAL_MISMATCH" and a["decision"] == "deny" for a in audits)


@pytest.mark.asyncio
async def test_p0_rag_allow_read_false_enforcement(tmp_path: Path) -> None:
    ws_dir = tmp_path / "workspace_noread"
    ws_dir.mkdir()
    doc = ws_dir / "noread_doc.txt"
    doc.write_text("Dokumen tanpa izin baca.", encoding="utf-8")

    db = DatabaseManager(db_path=tmp_path / "test.db")
    await db.initialize()
    await db.upsert_workspace({
        "id": "ws_noread",
        "name": "Workspace No Read",
        "folder_path": str(ws_dir),
        "owner_id": "alice_id",
        "allow_read": False,
    })
    store = HybridRAGStore(db=db, vector_dir=tmp_path / "vectors")

    with pytest.raises(PermissionError) as exc_info:
        await store.index_workspace_folder("ws_noread", principal_id="alice_id")
    assert "Izin baca (read) tidak diaktifkan" in str(exc_info.value)

    with pytest.raises(PermissionError) as exc_info:
        await store.index_file("ws_noread", doc, principal_id="alice_id")
    assert "Izin baca (read) tidak diaktifkan" in str(exc_info.value)

    # Verify audit event logged for read permission denied
    audits = await db.list_permission_audit_events(limit=10)
    assert any(a["reason_code"] == "READ_PERMISSION_DENIED" and a["decision"] == "deny" for a in audits)


@pytest.mark.asyncio
async def test_p0_rag_rest_endpoints_boundary_and_principal_enforcement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import app.api.routes as routes_mod

    isolated_db = DatabaseManager(db_path=tmp_path / "rag_api_test.db")
    await isolated_db.initialize()
    isolated_rag = HybridRAGStore(db=isolated_db, vector_dir=tmp_path / "rag_api_vectors")
    monkeypatch.setattr(routes_mod, "db_manager", isolated_db)
    monkeypatch.setattr(routes_mod, "rag_store", isolated_rag)

    orig_dev = settings.dev_mode
    orig_token = settings.auth_token
    try:
        settings.dev_mode = False
        settings.auth_token = "aksa-prod-token-test-boundary-12345"

        app = create_app()
        transport = ASGITransport(app=app)
        auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}

        async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
            ws_dir = tmp_path / "api_ws"
            ws_dir.mkdir()
            (ws_dir / "valid_item.txt").write_text("Konten sah untuk API.", encoding="utf-8")

            outside_dir = tmp_path / "api_outside"
            outside_dir.mkdir()
            (outside_dir / "stolen.txt").write_text("STOLEN_CONTENT", encoding="utf-8")

            # 1. Register workspace with owner_id = principal_1
            resp_reg = await client.post(
                "/api/v1/workspaces",
                json={"name": "API WS", "folder_path": str(ws_dir), "allow_read": True},
                headers={"X-Principal-ID": "principal_1", **auth_headers},
            )
            assert resp_reg.status_code == 200
            ws_id = resp_reg.json()["workspace"]["id"]

            # 2. List files as principal_2 -> 403 Forbidden
            resp_list_wrong = await client.get(
                f"/api/v1/workspaces/{ws_id}/files",
                headers={"X-Principal-ID": "principal_2", **auth_headers},
            )
            assert resp_list_wrong.status_code == 403
            assert "Principal tidak memiliki izin" in resp_list_wrong.json()["detail"]

            # 3. List files as principal_1 -> 200 OK
            resp_list_ok = await client.get(
                f"/api/v1/workspaces/{ws_id}/files",
                headers={"X-Principal-ID": "principal_1", **auth_headers},
            )
            assert resp_list_ok.status_code == 200
            assert any(f["name"] == "valid_item.txt" for f in resp_list_ok.json()["files"])

            # 4. Attempt to index folder outside workspace via traversal -> 403 Forbidden
            resp_idx_bad = await client.post(
                "/api/v1/rag/index-folder",
                json={"workspace_id": ws_id, "folder_path": str(outside_dir)},
                headers={"X-Principal-ID": "principal_1", **auth_headers},
            )
            assert resp_idx_bad.status_code == 403
            assert "berada di luar Folder Kerja" in resp_idx_bad.json()["detail"]

            # 5. Attempt to index with encoded traversal -> 403 Forbidden
            resp_idx_encoded = await client.post(
                "/api/v1/rag/index-folder",
                json={"workspace_id": ws_id, "folder_path": "%2e%2e%2fapi_outside"},
                headers={"X-Principal-ID": "principal_1", **auth_headers},
            )
            assert resp_idx_encoded.status_code == 403

            # 6. Index valid workspace root -> 200 OK
            resp_idx_ok = await client.post(
                "/api/v1/rag/index-folder",
                json={"workspace_id": ws_id},
                headers={"X-Principal-ID": "principal_1", **auth_headers},
            )
            assert resp_idx_ok.status_code == 200
            assert resp_idx_ok.json()["indexed"] >= 1
    finally:
        settings.dev_mode = orig_dev
        settings.auth_token = orig_token


@pytest.mark.asyncio
async def test_p0_rag_error_never_leaks_private_file_existence(tmp_path: Path) -> None:
    ws_dir = tmp_path / "ws_leak_test"
    ws_dir.mkdir()
    outside_dir = tmp_path / "outside_secret"
    outside_dir.mkdir()

    existing_private = outside_dir / "really_exists.txt"
    existing_private.write_text("CONFIDENTIAL", encoding="utf-8")
    nonexistent_private = outside_dir / "does_not_exist_xyz.txt"

    # Both existing and non-existing private files must result in the same generic SandboxViolationError
    with pytest.raises(SandboxViolationError) as exc1:
        canonicalize_and_validate_path(str(existing_private), ws_dir)

    with pytest.raises(SandboxViolationError) as exc2:
        canonicalize_and_validate_path(str(nonexistent_private), ws_dir)

    # Identical error text, no leakage of existence
    assert str(exc1.value) == str(exc2.value)
    assert "Akses ditolak oleh Sandbox AKSA" in str(exc1.value)
