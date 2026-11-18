"""Phase 4 & Phase 5 Verification Suite: Local Hybrid RAG (RRF), Multi-Tier Memory, and Telegram Gateway."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.sandbox import RiskLevel, WorkspacePolicy, sandbox_manager
from app.db.models import DatabaseManager, db_manager
from app.db.seed import seed_default_indonesian_team
from app.main import app
from app.rag.store import HybridRAGStore
from app.rag.watcher import WorkspaceRAGWatcher
from app.telegram.auth import TelegramAuthGuard
from app.telegram.bot import telegram_gateway
from app.tools import tool_registry


@pytest.mark.asyncio
async def test_phase4_hybrid_rag_rrf_and_incremental_sha256(tmp_path: Path) -> None:
    """Verify structure-aware ingestion, SHA-256 incremental indexing, and Hybrid Vector + FTS5 RRF search."""
    db_file = tmp_path / "rag_test.db"
    vec_dir = tmp_path / "lancedb_vec"
    db = DatabaseManager(db_path=db_file)
    await db.initialize()

    ws = await db.upsert_workspace(
        {"name": "Arsip Kantor", "folder_path": str(tmp_path / "arsip")}
    )
    ws_dir = Path(ws["folder_path"])
    ws_dir.mkdir(parents=True, exist_ok=True)

    doc1 = ws_dir / "SK_Direksi_2026.md"
    doc1.write_text(
        "# Surat Keputusan Direksi\n"
        "Nomor Surat Resmi: SK-DIR/089/2026 tentang Anggaran Transformasi AI Nusantara.\n"
        "Total alokasi dana sebesar Rp 450.000.000 untuk kuartal keempat.",
        encoding="utf-8",
    )

    csv1 = ws_dir / "Data_Vendor.csv"
    csv1.write_text(
        "kode_vendor,nama_perusahaan,status\n"
        "VND-991,PT Sinar Teknologi Mandiri,Aktif\n"
        "VND-992,CV Karya Nusantara,Evaluasi\n",
        encoding="utf-8",
    )

    store = HybridRAGStore(db=db, vector_dir=vec_dir)

    # First index run -> both files indexed
    res1 = await store.index_file(ws["id"], doc1)
    assert res1["status"] == "indexed"
    assert res1["chunk_count"] >= 1

    # Second index run without file modification -> skipped via SHA-256 diff check
    res1_repeat = await store.index_file(ws["id"], doc1)
    assert res1_repeat["status"] == "unchanged"

    # Full workspace folder index
    folder_stats = await store.index_workspace_folder(ws["id"], ws_dir)
    assert folder_stats["indexed"] == 1  # csv1 is newly indexed
    assert folder_stats["unchanged"] == 1  # doc1 was unchanged

    # Hybrid Search (Vector + FTS5 BM25 via RRF) for exact Indonesian letter number
    hits = await store.hybrid_search("SK-DIR/089/2026", workspace_id=ws["id"], top_k=3)
    assert len(hits) >= 1
    assert "SK-DIR/089/2026" in hits[0]["content"]
    assert hits[0]["rrf_score"] > 0

    # Multi-Tier Memory (SQLite user_memories + .aksa/MEMORY.md)
    mem = await store.remember_user_fact(
        fact="Format mata uang wajib menggunakan Rp dengan titik pemisah ribuan.",
        category="standar_dokumen",
        workspace_id=ws["id"],
        workspace_folder=ws_dir,
    )
    assert mem["category"] == "standar_dokumen"
    assert (ws_dir / ".aksa" / "MEMORY.md").exists()

    recalled = await store.recall_user_memories(query="mata uang")
    assert len(recalled) == 1

    # Watchdog start & stop check
    watcher = WorkspaceRAGWatcher(store=store)
    started = watcher.start_watching(ws["id"], ws_dir)
    assert started is True
    watcher.stop_all()


@pytest.mark.asyncio
async def test_phase5_telegram_security_voice_files_and_hitl(tmp_path: Path) -> None:
    """Verify 6-digit pairing, strict numeric ID whitelist, voice notes, file upload, and HITL callbacks."""
    db_manager.db_path = tmp_path / "tg_engine.db"
    await db_manager.initialize()
    await seed_default_indonesian_team(db_manager)

    sandbox_manager.register_workspace(
        WorkspacePolicy(
            folder_path=str(tmp_path),
            allow_read=True,
            allow_write=True,
            allow_execute=True,
        )
    )

    guard = TelegramAuthGuard()
    handler = telegram_gateway.handler
    handler.auth = guard

    intruder_id = 999888777
    owner_id = 123456789

    # 1. Unknown user message must be blocked and ignored
    blocked_res = await handler.handle_incoming_message(
        telegram_user_id=intruder_id,
        text="Buatkan file rahasia",
        username="hacker_asing",
        workspace_path=str(tmp_path),
    )
    assert blocked_res["authorized"] is False
    assert blocked_res.get("ignored") is True

    # 2. Wrong 6-digit pairing code fails
    wrong_pair = await handler.handle_incoming_message(
        telegram_user_id=owner_id,
        text="/pair 000000",
        username="budi_owner",
    )
    assert wrong_pair["authorized"] is False

    # 3. Correct 6-digit pairing code locks whitelist to owner_id
    correct_code = guard.pairing_code
    ok_pair = await handler.handle_incoming_message(
        telegram_user_id=owner_id,
        text=f"/pair {correct_code}",
        username="budi_owner",
    )
    assert ok_pair["authorized"] is True
    assert guard.is_authorized(owner_id) is True

    # 4. Subsequent pairing attempt by another user is rejected because pairing mode locked
    locked_pair = await handler.handle_incoming_message(
        telegram_user_id=intruder_id,
        text=f"/pair {correct_code}",
        username="intruder2",
    )
    assert locked_pair["authorized"] is False

    # 5. Authorized owner executes Indonesian Voice Note -> creates Excel artifact in workspace
    voice_res = await handler.handle_voice_note(
        telegram_user_id=owner_id,
        audio_bytes_or_hint="Tolong buatkan rekap anggaran di Excel",
        username="budi_owner",
        workspace_path=str(tmp_path),
    )
    assert voice_res["authorized"] is True
    assert "Pesan Suara Diterima" in voice_res["reply"]
    assert len(voice_res["artifacts"]) == 1

    # 6. Incoming file upload from Telegram -> saved to Inbox_Telegram & indexed into RAG
    ws_record = await telegram_gateway._orchestrator.db.upsert_workspace(
        {"name": "Folder Telegram", "folder_path": str(tmp_path)}
    )
    upload_res = await handler.handle_incoming_file(
        telegram_user_id=owner_id,
        file_name="Memo_Lapangan.txt",
        file_bytes=b"# Memo Lapangan\nPengiriman logistik tahap 2 berjalan lancar.",
        workspace_id=ws_record["id"],
        workspace_path=str(tmp_path),
        caption="Simpan ke arsip",
    )
    assert upload_res["authorized"] is True
    assert Path(upload_res["saved_path"]).exists()

    # 7. Remote HITL Approval callback from Telegram
    hitl_req = await sandbox_manager.create_hitl_request(
        tool_name="run_custom_python_task",
        title_id="Izin Skrip Jarak Jauh",
        description_id="Konfirmasi dari Telegram",
        risk_level=RiskLevel.HIGH,
    )
    cb_res = await handler.handle_hitl_callback(
        telegram_user_id=owner_id,
        request_id=hitl_req.id,
        approved=True,
    )
    assert cb_res["authorized"] is True
    assert cb_res["status"] == "approved"


@pytest.mark.asyncio
async def test_phase4_and_phase5_rest_endpoints(tmp_path: Path) -> None:
    """Verify REST endpoints for RAG search, memories, and Telegram gateway configuration."""
    db_manager.db_path = tmp_path / "rest_phase45.db"
    await db_manager.initialize()
    await seed_default_indonesian_team(db_manager)

    transport = ASGITransport(app=app)
    auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        # Memory endpoints
        resp_mem = await client.post(
            "/api/v1/memories",
            json={"fact": "Direktur Utama adalah Bapak Hendra Wijaya", "category": "profil"},
        )
        assert resp_mem.status_code == 200

        resp_list_mem = await client.get("/api/v1/memories", params={"query": "Hendra"})
        assert resp_list_mem.status_code == 200
        assert len(resp_list_mem.json()["memories"]) >= 1

        # Telegram configuration & status endpoints
        resp_tg_cfg = await client.post(
            "/api/v1/telegram/configure",
            json={"bot_token": "12345678:AAH_test_token_nusantara"},
        )
        assert resp_tg_cfg.status_code == 200
        assert resp_tg_cfg.json()["connected"] is True

        # Registered RAG tools check
        res_tool = await tool_registry.execute("recall_user_memories", query="Hendra")
        assert res_tool.success is True
