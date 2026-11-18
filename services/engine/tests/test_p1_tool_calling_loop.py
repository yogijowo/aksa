"""Tests for P1-1: Native Tool-Calling & LLM Execution Loop."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
import openpyxl

from app.core.llm_router import UnifiedLLMRouter
from app.core.orchestrator import HierarchicalOrchestrator
from app.core.sandbox import WorkspacePolicy, sandbox_manager
from app.db.models import DatabaseManager
from app.db.seed import seed_default_indonesian_team


@pytest.fixture
async def orchestrator_setup(tmp_path: Path):
    db = DatabaseManager(db_path=tmp_path / "p1_1_test.db")
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

    return orchestrator, ws_dir, router


@pytest.mark.asyncio
async def test_p1_tool_calling_csv_to_excel_with_sum_row(orchestrator_setup) -> None:
    """Verify that a tool call converts a CSV into an Excel file containing a SUM row."""
    orchestrator, ws_dir, router = orchestrator_setup

    # 1. Create a sample CSV file
    csv_file = ws_dir / "penjualan.csv"
    csv_file.write_text(
        "No,Barang,Jumlah,Harga,Total\n"
        "1,Buku,10,5000,50000\n"
        "2,Pulpen,20,3000,60000\n"
        "3,Penghapus,5,2000,10000\n",
        encoding="utf-8",
    )

    excel_target = ws_dir / "rekap_penjualan.xlsx"

    # Mock the LLM to emit tool_calls on the first step, then finish with text on the second step
    first_resp = {
        "content": "",
        "tool_calls": [
            {
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "excel_create_workbook",
                    "arguments": json.dumps({
                        "file_path": str(excel_target),
                        "csv_source_path": str(csv_file),
                    }),
                },
            }
        ],
        "input_tokens": 100,
        "output_tokens": 40,
        "simulated": False,
        "cloud_called": False,
        "provider_used": "mock",
    }
    second_resp = {
        "content": "Berkas rekap_penjualan.xlsx berhasil dibuat dengan ringkasan SUM dari penjualan.csv.",
        "tool_calls": [],
        "input_tokens": 150,
        "output_tokens": 50,
        "simulated": False,
        "cloud_called": False,
        "provider_used": "mock",
    }

    with patch.object(router, "complete", side_effect=[first_resp, second_resp, second_resp]):
        result = await orchestrator.execute_hierarchical_task(
            prompt="tolong buatkan tabel rekap penjualan dari penjualan.csv",
            workspace_path=str(ws_dir),
        )

    # Verify Excel was created
    assert excel_target.exists()
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["name"] == "rekap_penjualan.xlsx"

    # Verify Excel contains the SUM row
    wb = openpyxl.load_workbook(excel_target)
    ws = wb.active
    # Row 1: Header, Rows 2-4: Data, Row 5: SUM row
    cell_val = str(ws["E5"].value)
    assert "=SUM" in cell_val
    wb.close()


@pytest.mark.asyncio
async def test_p1_tool_calling_conversational_creates_no_files(orchestrator_setup) -> None:
    """Verify that conversational prompts like 'ubah nada jawabanmu' create zero files."""
    orchestrator, ws_dir, router = orchestrator_setup

    files_before = set(ws_dir.iterdir())

    resp = {
        "content": "Tentu, mulai sekarang gaya bicara saya akan lebih santai dan bersahabat.",
        "tool_calls": [],
        "input_tokens": 80,
        "output_tokens": 30,
        "simulated": False,
        "cloud_called": False,
        "provider_used": "mock",
    }

    with patch.object(router, "complete", return_value=resp):
        result = await orchestrator.execute_hierarchical_task(
            prompt="ubah nada jawabanmu jadi lebih santai",
            workspace_path=str(ws_dir),
        )

    # 1. Zero artifacts reported
    assert len(result["artifacts"]) == 0

    # 2. Reply contains conversation response
    assert "santai" in result["reply"].lower()

    # 3. Workspace is 100% unchanged
    files_after = set(ws_dir.iterdir())
    assert files_after == files_before


@pytest.mark.asyncio
async def test_p1_tool_calling_write_outside_workspace_denied(orchestrator_setup) -> None:
    """Verify that a tool call attempting to write outside the authorized workspace is denied."""
    orchestrator, ws_dir, router = orchestrator_setup

    outside_target = ws_dir.parent / "unauthorized_secret.xlsx"

    first_resp = {
        "content": "",
        "tool_calls": [
            {
                "id": "call_malicious",
                "type": "function",
                "function": {
                    "name": "excel_create_workbook",
                    "arguments": json.dumps({"file_path": str(outside_target)}),
                },
            }
        ],
        "input_tokens": 100,
        "output_tokens": 40,
        "simulated": False,
        "cloud_called": False,
        "provider_used": "mock",
    }
    second_resp = {
        "content": "Maaf, akses penulisan di luar folder kerja ditolak oleh sistem keamanan AKSA.",
        "tool_calls": [],
        "input_tokens": 120,
        "output_tokens": 30,
        "simulated": False,
        "cloud_called": False,
        "provider_used": "mock",
    }

    call_count = 0

    async def mock_complete(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return first_resp
        return second_resp

    with patch.object(router, "complete", side_effect=mock_complete):
        result = await orchestrator.execute_hierarchical_task(
            prompt="buatkan file di luar folder kerja",
            workspace_path=str(ws_dir),
        )

    # 1. Zero artifacts created
    assert len(result["artifacts"]) == 0

    # 2. File was NOT created outside workspace
    assert not outside_target.exists()


@pytest.mark.asyncio
async def test_p1_no_auto_pdf_attachment_on_loose_keyword(orchestrator_setup) -> None:
    """Verify P1-6: PDFs in workspace are never auto-attached on loose keywords like 'apa' or 'isi'."""
    orchestrator, ws_dir, router = orchestrator_setup

    # Create dummy PDF files in workspace
    pdf1 = ws_dir / "laporan_rahasia_1.pdf"
    pdf1.write_bytes(b"%PDF-1.4 dummy confidential content 1")
    pdf2 = ws_dir / "laporan_rahasia_2.pdf"
    pdf2.write_bytes(b"%PDF-1.4 dummy confidential content 2")

    captured_attachments = []

    async def mock_complete(*args, **kwargs):
        captured_attachments.extend(kwargs.get("attachments") or [])
        return {
            "content": "Halo! Kabar saya baik. Ada yang bisa saya bantu di folder kerja ini?",
            "tool_calls": [],
            "input_tokens": 50,
            "output_tokens": 20,
            "simulated": False,
            "cloud_called": False,
            "provider_used": "mock",
        }

    with patch.object(router, "complete", side_effect=mock_complete):
        res = await orchestrator.execute_hierarchical_task(
            prompt="apa kabar? apa isi dokumen di folder kerja?",
            workspace_path=str(ws_dir),
        )

    # Acceptance check: ZERO attachments sent to router
    assert len(captured_attachments) == 0
    assert "Halo! Kabar saya baik" in res["reply"]
