"""Test clean document generation and multi-agent delegation without dummy sample data."""

import pytest
from pathlib import Path
from docx import Document

from app.core.sandbox import WorkspacePolicy, sandbox_manager
from app.tools.registry import tool_registry
from app.db.models import DatabaseManager
from app.core.llm_router import UnifiedLLMRouter
from app.core.orchestrator import HierarchicalOrchestrator


@pytest.mark.asyncio
async def test_word_create_document_no_sample_data(tmp_path: Path):
    sandbox_manager.register_workspace(
        WorkspacePolicy(
            folder_path=str(tmp_path),
            allow_read=True,
            allow_write=True,
            allow_execute=True,
        )
    )

    doc_path = tmp_path / "test_mou.docx"
    res = await tool_registry.execute(
        "word_create_document",
        file_path=str(doc_path),
        title="MEMORANDUM OF UNDERSTANDING (MoU) KERJASAMA",
        style_preset="surat_resmi",
    )
    assert res.success is True
    assert doc_path.exists()

    doc = Document(str(doc_path))
    full_text = "\n".join(p.text for p in doc.paragraphs)

    # Verify no dummy company or sample AKSA text
    assert "PT NUSANTARA DIGITAL MANDIRI" not in full_text
    assert "Dokumen ini disusun secara otomatis oleh Spesialis Administrasi & Office AKSA" not in full_text
    assert "MEMORANDUM OF UNDERSTANDING (MoU) KERJASAMA" in full_text


def test_select_relevant_sub_agents_targeted():
    db = DatabaseManager(Path("/tmp/test_aksa_dummy.db"))
    router = UnifiedLLMRouter(db)
    orchestrator = HierarchicalOrchestrator(db, router)

    sub_agents = [
        {"id": "agt_1", "name": "Peneliti Dokumen", "role_title": "Riset RAG", "tool_categories": ["rag_search", "filesystem"]},
        {"id": "agt_2", "name": "Spesialis Word", "role_title": "Pembuat Word", "tool_categories": ["office_word", "filesystem"]},
        {"id": "agt_3", "name": "Operator PC", "role_title": "Automasi PC", "tool_categories": ["os_automation", "uv_python", "filesystem"]},
        {"id": "agt_4", "name": "Sub-Agen C", "role_title": "Agen Khusus", "tool_categories": ["filesystem"]},
    ]

    # Prompt: "bisa carikan refrensi surat MOU lalu buatkan suratnya beriupa docs?"
    selected = orchestrator._select_relevant_sub_agents(
        "bisa carikan refrensi surat MOU lalu buatkan suratnya beriupa docs?",
        sub_agents,
    )

    selected_ids = [a["id"] for a in selected]
    # Researcher (agt_1) and Word specialist (agt_2) should be selected
    assert "agt_1" in selected_ids
    assert "agt_2" in selected_ids
    # Operator PC and duplicate generic Sub-Agen C should NOT be selected
    assert "agt_3" not in selected_ids
    assert "agt_4" not in selected_ids
    assert len(selected) == 2


@pytest.mark.asyncio
async def test_ppt_generation_with_excel_context(tmp_path: Path):
    import openpyxl
    from pptx import Presentation

    sandbox_manager.register_workspace(
        WorkspacePolicy(
            folder_path=str(tmp_path),
            allow_read=True,
            allow_write=True,
            allow_execute=True,
        )
    )

    # 1. Create a sample Excel file kk.xlsx in the workspace
    excel_path = tmp_path / "kk.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rekap_Penjualan"
    ws.append(["ID", "Nama Produk", "Kategori", "Jumlah Terjual"])
    ws.append(["P01", "Paket Premium", "Layanan", 150])
    ws.append(["P02", "Paket Bisnis", "Layanan", 85])
    wb.save(excel_path)
    wb.close()

    from app.db.seed import seed_default_indonesian_team

    db = DatabaseManager(tmp_path / "test_aksa_session.db")
    await db.initialize()
    await seed_default_indonesian_team(db)
    await db.upsert_workspace({
        "id": "ws_test_ppt",
        "name": "Folder Test",
        "folder_path": str(tmp_path),
        "allow_read": 1,
        "allow_write": 1,
        "allow_execute": 0,
    })

    router = UnifiedLLMRouter(db)
    orchestrator = HierarchicalOrchestrator(db, router)

    # 2. Execute task with prior conversation history mentioning kk.xlsx
    result = await orchestrator.execute_hierarchical_task(
        prompt="bisa buatkan jadi presentasi ppt?",
        workspace_id="ws_test_ppt",
        workspace_path=str(tmp_path),
        conversation_history=[
            {
                "role": "assistant",
                "content": "Untuk mengoptimalkan data dalam kk.xlsx, saya dapat membantu menganalisis isi sel dan sheet tersebut.",
            }
        ],
    )

    assert result.get("status") == "success" or len(result.get("artifacts", [])) > 0
    pptx_artifacts = [a for a in result.get("artifacts", []) if a.get("file_type") == "pptx"]
    assert len(pptx_artifacts) >= 1

    created_ppt = Path(pptx_artifacts[0]["file_path"])
    assert created_ppt.exists()
    prs = Presentation(str(created_ppt))
    assert len(prs.slides) >= 3

    # Check slide texts contain references to kk.xlsx or the data
    all_slide_text = ""
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                all_slide_text += " " + shape.text_frame.text
            elif shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        all_slide_text += " " + cell.text

    assert "kk.xlsx" in all_slide_text or "Rekap_Penjualan" in all_slide_text or "Nama Produk" in all_slide_text
