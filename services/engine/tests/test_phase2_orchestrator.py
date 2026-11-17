"""Tests for Phase 2: UnifiedLLMRouter, TokenOptimizer, and HierarchicalOrchestrator."""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.llm_router import UnifiedLLMRouter
from app.core.orchestrator import HierarchicalOrchestrator
from app.core.token_optimizer import token_optimizer
from app.db.models import DatabaseManager
from app.db.seed import seed_default_indonesian_team


def test_lazy_tool_loading_and_handback_isolation() -> None:
    tools, saved = token_optimizer.get_lazy_tools_for_agent(["office_excel", "filesystem"])
    assert len(tools) == 3
    assert saved > 3000

    summary, metrics = token_optimizer.compact_subagent_handback(
        raw_subagent_output="Rekap keuangan selesai dibuat di Rekap.xlsx dengan total Rp 125.000.000.",
        Simulated_document_tokens_processed=5000,
        lazy_tool_tokens_saved=saved,
    )
    assert "Rekap.xlsx" in summary
    assert metrics.total_tokens_saved > 7000


@pytest.mark.asyncio
async def test_llm_router_and_hierarchical_orchestrator(tmp_path: Path) -> None:
    db = DatabaseManager(db_path=tmp_path / "phase2_test.db")
    await db.initialize()
    await seed_default_indonesian_team(db)

    router = UnifiedLLMRouter(db=db)
    await router.save_api_key("deepseek", "sk-test-key-123")
    saved_keys = await router.get_saved_api_keys()
    assert saved_keys.get("deepseek") == "sk-test-key-123"

    providers = await router.list_providers_status()
    assert any(p["id"] == "ollama" and p["is_local"] for p in providers)
    assert any(p["id"] == "deepseek" and p["configured"] for p in providers)

    orchestrator = HierarchicalOrchestrator(db=db, llm_router=router)
    result = await orchestrator.execute_hierarchical_task(
        prompt="Baca dokumen laporan di folder ini dan buatkan rekap Excel bulanan",
        workspace_path=str(tmp_path),
    )

    assert result["supervisor_name"] == "Manajer Eksekutif"
    assert len(result["execution_steps"]) >= 1
    assert result["tokens_saved"] > 3000
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["file_type"] == "xlsx"

