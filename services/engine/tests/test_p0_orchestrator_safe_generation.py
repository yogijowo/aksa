"""Tests for P0-6: Safe Document Generation, No-Overwrite Guard, Multi-PDF Disambiguation, and Accurate Size Reporting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest
import docx
from reportlab.lib import pagesizes as ps
from reportlab.pdfgen import canvas

from app.core.llm_router import UnifiedLLMRouter
from app.core.orchestrator import HierarchicalOrchestrator, _generate_non_colliding_path
from app.core.sandbox import WorkspacePolicy, sandbox_manager
from app.db.models import DatabaseManager
from app.db.seed import seed_default_indonesian_team


def _create_sample_pdf(file_path: Path, title: str, text: str) -> None:
    """Helper to generate a valid PDF file with real content for tests."""
    c = canvas.Canvas(str(file_path), pagesize=ps.A4)
    c.drawString(100, 750, title)
    c.drawString(100, 700, text)
    c.save()


@pytest.fixture
async def orchestrator_setup(tmp_path: Path):
    db = DatabaseManager(db_path=tmp_path / "p0_6_test.db")
    await db.initialize()
    await seed_default_indonesian_team(db)
    router = UnifiedLLMRouter(db=db)
    orchestrator = HierarchicalOrchestrator(db=db, llm_router=router)

    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    sandbox_manager.register_workspace(
        WorkspacePolicy(
            workspace_id="ws_test",
            folder_path=str(ws_dir),
            allow_write=True,
            allow_read=True,
        )
    )

    return orchestrator, ws_dir


def test_generate_non_colliding_path(tmp_path: Path) -> None:
    """Verify that _generate_non_colliding_path avoids overwriting existing files."""
    test_dir = tmp_path / "non_collide_test"
    test_dir.mkdir()

    p0 = _generate_non_colliding_path(test_dir, "Laporan", "docx")
    assert p0.name == "Laporan.docx"
    p0.write_text("v0", encoding="utf-8")

    p1 = _generate_non_colliding_path(test_dir, "Laporan", "docx")
    assert p1.name == "Laporan (1).docx"
    p1.write_text("v1", encoding="utf-8")

    p2 = _generate_non_colliding_path(test_dir, "Laporan", "docx")
    assert p2.name == "Laporan (2).docx"


@pytest.mark.asyncio
async def test_preserve_existing_docx_on_duplication(orchestrator_setup) -> None:
    """Verify that an existing X.docx is NEVER overwritten when duplicating X.pdf."""
    orchestrator, ws_dir = orchestrator_setup

    pdf_file = ws_dir / "Laporan_Kinerja.pdf"
    _create_sample_pdf(pdf_file, "LAPORAN KINERJA RESMI", "Isi konten evaluasi program.")

    existing_docx = ws_dir / "Laporan_Kinerja.docx"
    original_text = "DOKUMEN ASLI YANG SUDAH DIEDIT SECARA MANUAL - JANGAN DIHAPUS!"
    doc = docx.Document()
    doc.add_paragraph(original_text)
    doc.save(str(existing_docx))
    original_mtime = existing_docx.stat().st_mtime

    result = await orchestrator.execute_hierarchical_task(
        prompt="tolong duplikasi Laporan_Kinerja.pdf jadi word",
        workspace_path=str(ws_dir),
    )

    # 1. Verify original docx was NOT overwritten
    assert existing_docx.exists()
    doc_check = docx.Document(str(existing_docx))
    assert doc_check.paragraphs[0].text == original_text
    assert existing_docx.stat().st_mtime == original_mtime

    # 2. Verify non-colliding duplicate was created
    new_duplicate = ws_dir / "Laporan_Kinerja (1).docx"
    assert new_duplicate.exists()
    assert new_duplicate.stat().st_size > 0

    # 3. Verify artifact returned points to the new non-colliding file
    assert len(result["artifacts"]) == 1
    art = result["artifacts"][0]
    assert art["name"] == "Laporan_Kinerja (1).docx"
    assert art["file_type"] == "docx"
    assert art["size_label"] != "42 KB"
    assert "KB" in art["size_label"]


@pytest.mark.asyncio
async def test_failed_tool_returns_no_artifacts_and_reports_failure(orchestrator_setup) -> None:
    """Verify that a tool failure returns no artifacts and reports the failure honestly."""
    orchestrator, ws_dir = orchestrator_setup

    pdf_file = ws_dir / "Dokumen_Rusak.pdf"
    _create_sample_pdf(pdf_file, "RUSAK", "Percobaan kegagalan.")

    with patch(
        "app.core.orchestrator._create_word_duplicate_from_pdf",
        side_effect=RuntimeError("Gagal membaca struktur halaman PDF yang rusak."),
    ):
        result = await orchestrator.execute_hierarchical_task(
            prompt="duplikasi Dokumen_Rusak.pdf ke format word",
            workspace_path=str(ws_dir),
        )

    # 1. No artifacts reported
    assert len(result["artifacts"]) == 0

    # 2. Reply reports failure honestly
    assert "Gagal" in result["reply"] or "kendala" in result["reply"].lower()
    assert "Dokumen_Rusak" in result["reply"] or "rusak" in result["reply"].lower()

    # 3. No half-written or 0-byte docx file left in workspace
    docx_files = list(ws_dir.glob("*.docx"))
    assert len(docx_files) == 0


@pytest.mark.asyncio
async def test_ambiguous_multi_pdf_duplication_clarification(orchestrator_setup) -> None:
    """Verify that multiple PDFs with an ambiguous prompt returns clarification and leaves workspace unchanged."""
    orchestrator, ws_dir = orchestrator_setup

    pdf1 = ws_dir / "Sounding_Market_DPRD.pdf"
    pdf2 = ws_dir / "Nota_Dinas_Bupati.pdf"
    _create_sample_pdf(pdf1, "SOUNDING MARKET", "Rencana pengadaan barang.")
    _create_sample_pdf(pdf2, "NOTA DINAS", "Arahan pimpinan daerah.")

    # Record directory state before execution
    files_before = set(ws_dir.iterdir())

    # Ambiguous prompt without specifying which PDF
    result = await orchestrator.execute_hierarchical_task(
        prompt="buatkan file duplikasi sama persis tapi jadi word",
        workspace_path=str(ws_dir),
    )

    # 1. Zero artifacts reported
    assert len(result["artifacts"]) == 0

    # 2. Clarification question returned
    assert "Sounding_Market_DPRD.pdf" in result["reply"]
    assert "Nota_Dinas_Bupati.pdf" in result["reply"]
    assert any(k in result["reply"].lower() for k in ("pilih", "sebutkan", "tentukan", "mana"))

    # 3. Workspace is completely unchanged
    files_after = set(ws_dir.iterdir())
    assert files_after == files_before
    assert len(list(ws_dir.glob("*.docx"))) == 0


@pytest.mark.asyncio
async def test_multi_pdf_disambiguation_when_specified(orchestrator_setup) -> None:
    """Verify that when multiple PDFs exist, mentioning one specifically duplicates only that file."""
    orchestrator, ws_dir = orchestrator_setup

    pdf1 = ws_dir / "Sounding_Market_DPRD.pdf"
    pdf2 = ws_dir / "Nota_Dinas_Bupati.pdf"
    _create_sample_pdf(pdf1, "SOUNDING MARKET", "Rencana pengadaan.")
    _create_sample_pdf(pdf2, "NOTA DINAS", "Nota dinas bupati.")

    result = await orchestrator.execute_hierarchical_task(
        prompt="tolong duplikasi file Nota_Dinas_Bupati ke format word",
        workspace_path=str(ws_dir),
    )

    # 1. Exactly one artifact for the specified file
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["name"] == "Nota_Dinas_Bupati.docx"

    # 2. Only Nota_Dinas_Bupati.docx was created, not Sounding_Market_DPRD.docx
    assert (ws_dir / "Nota_Dinas_Bupati.docx").exists()
    assert not (ws_dir / "Sounding_Market_DPRD.docx").exists()
