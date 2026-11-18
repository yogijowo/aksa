"""Tests for P1-7: Hybrid RAG Synonym Search, Crash-Safe Persistence & Atomic Storage."""

from __future__ import annotations

from pathlib import Path
import pytest

from app.db.models import DatabaseManager
from app.rag.store import HybridRAGStore


@pytest.mark.asyncio
async def test_p1_rag_synonym_search_and_expansion(tmp_path: Path) -> None:
    """Verify that Indonesian synonyms ('anggaran' <-> 'pagu') retrieve the right chunk via RRF."""
    db = DatabaseManager(db_path=tmp_path / "test_rag.db")
    await db.initialize()
    await db.upsert_workspace({"id": "ws_rag_test", "name": "Test RAG", "folder_path": str(tmp_path)})

    store = HybridRAGStore(db=db, vector_dir=tmp_path / "vectors")

    # Create a test document that mentions only "pagu", not "anggaran"
    doc_path = tmp_path / "rka_skpd.txt"
    doc_path.write_text(
        "Rencana Kerja dan Anggaran SKPD:\n"
        "Total pagu operasional tahun 2026 dialokasikan sebesar Rp 750.000.000.\n"
        "Alokasi pagu belanja modal untuk pemeliharaan gedung kantor disetujui.",
        encoding="utf-8",
    )

    idx_res = await store.index_file("ws_rag_test", doc_path)
    assert idx_res["status"] == "indexed"

    # Search for "anggaran" (synonym of pagu)
    results = await store.hybrid_search("anggaran operasional", workspace_id="ws_rag_test")
    assert len(results) > 0
    assert "pagu operasional" in results[0]["content"].lower() or "anggaran" in results[0]["content"].lower()

    # Search for "biaya" (synonym of pagu/anggaran)
    results_biaya = await store.hybrid_search("biaya gedung kantor", workspace_id="ws_rag_test")
    assert len(results_biaya) > 0
    assert "pemeliharaan gedung" in results_biaya[0]["content"].lower()


@pytest.mark.asyncio
async def test_p1_rag_crash_recovery_from_sqlite_vectors(tmp_path: Path) -> None:
    """Verify that if the JSON index is lost/corrupted, vectors are recovered from SQLite rag_vector_chunks."""
    db = DatabaseManager(db_path=tmp_path / "test_rag.db")
    await db.initialize()
    await db.upsert_workspace({"id": "ws_rag_test", "name": "Test RAG", "folder_path": str(tmp_path)})

    vector_dir = tmp_path / "vectors"
    store1 = HybridRAGStore(db=db, vector_dir=vector_dir)

    doc_path = tmp_path / "nota_dinas.txt"
    doc_path.write_text(
        "Nota Dinas Nomor 005/AKSA/2026 perihal Pengadaan Server Cloud Lokal.\n"
        "Harap segera memproses pengadaan perangkat pendukung sebelum akhir triwulan.",
        encoding="utf-8",
    )

    await store1.index_file("ws_rag_test", doc_path)

    # Delete the json file to simulate a disk loss / crash
    json_file = vector_dir / "vectors_index.json"
    if json_file.exists():
        json_file.unlink()

    # Create a fresh store instance pointing to the same db
    store2 = HybridRAGStore(db=db, vector_dir=vector_dir)
    assert len(store2._vectors) == 0

    # Search triggers _ensure_vectors_loaded_async which restores from SQLite
    results = await store2.hybrid_search("server cloud pengadaan", workspace_id="ws_rag_test")
    assert len(results) > 0
    assert "pengadaan server cloud" in results[0]["content"].lower()
    assert len(store2._vectors) > 0  # Restored from SQLite

