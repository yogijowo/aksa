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
