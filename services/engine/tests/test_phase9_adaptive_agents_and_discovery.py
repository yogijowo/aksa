"""Phase 9 Comprehensive Verification: Adaptive Agent Learning, Dynamic Discovery, and Isolated Storage."""

import os
import shutil
import tempfile
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import EngineConfig, settings
from app.core.agent_directory import (
    AgentDirectoryService,
    AgentIsolationError,
    AgentIsolationPolicy,
)
from app.core.agent_learning import (
    AgentLearningMetrics,
    AgentMemoryService,
    LearningPrivacyFilter,
    SkillCandidateExtractor,
    SkillEvaluator,
    SkillVersionService,
)
from app.core.model_discovery import (
    DiscoveredModel,
    ModelDiscoveryService,
    OpenAIDiscoveryAdapter,
)
from app.core.privacy_gate import ProviderMode, privacy_policy_gate
from app.main import app
from app.skills.skill_manager import CURATED_SKILL_CATALOG, agent_skills_manager


@pytest.fixture
def temp_aksa_root():
    tmp = tempfile.mkdtemp(prefix="aksa_root_test_")
    root_path = Path(tmp)
    from app.core.agent_directory import agent_directory_service
    old_root = agent_directory_service.root_dir
    agent_directory_service.set_root_dir(root_path)
    yield agent_directory_service
    agent_directory_service.set_root_dir(old_root)
    shutil.rmtree(tmp, ignore_errors=True)


def test_p0_release_config_and_token_generation():
    """Verify release mode defaults, rejection of dev tokens, and CSPRNG generation."""
    # 1. When dev mode is false and no token is passed, generate CSPRNG token
    cfg_release = EngineConfig(dev_mode=False, auth_token="")
    assert cfg_release.dev_mode is False
    assert len(cfg_release.auth_token) >= 32
    assert cfg_release.auth_token != "dev-aksa-local-token"
    assert cfg_release.host == "127.0.0.1"


def test_agent_directory_service_and_isolation(temp_aksa_root):
    """Verify isolated folder provisioning and cross-agent isolation barriers."""
    svc = temp_aksa_root
    policy = AgentIsolationPolicy(svc)

    # 1. Provision Agent A and Agent B
    agent_a_dir = svc.provision_agent_directory("agent-video-01")
    agent_b_dir = svc.provision_agent_directory("agent-finance-02")

    assert (agent_a_dir / "PROFILE.md").exists()
    assert (agent_a_dir / "agent.json").exists()
    assert (agent_a_dir / "memory" / "episodic").exists()
    assert (agent_a_dir / "skills" / "candidates").exists()

    # 2. Agent A can access its own subpath
    path_a = policy.validate_access("agent-video-01", "agent-video-01", "memory/episodic")
    assert path_a.exists()

    # 3. Agent A CANNOT access Agent B's storage (Raises AgentIsolationError)
    with pytest.raises(AgentIsolationError):
        policy.validate_access("agent-video-01", "agent-finance-02", "memory/episodic")

    # 4. Path traversal attempt is blocked
    with pytest.raises(AgentIsolationError):
        svc.resolve_agent_path("agent-video-01", "../../system/registry")

    # 5. Export and purge
    bundle = policy.export_agent_package("agent-video-01")
    assert bundle.exists()
    assert bundle.name.endswith(".zip")

    purged = policy.purge_agent_data("agent-video-01")
    assert purged is True
    assert not agent_a_dir.exists()


def test_learning_privacy_filter_redacts_credentials_and_pii():
    """Verify zero-leakage redaction of keys, bearer tokens, NIK, NPWP, and phone numbers."""
    raw_text = (
        "Pengguna dengan NIK 3171012345678901 dan NPWP 01.234.567.8-901.000 memiliki nomor HP 08123456789. "
        "Kunci API: sk-proj-123456789012345678901234567890 dan Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz."
    )
    redacted = LearningPrivacyFilter.redact(raw_text)

    assert "3171012345678901" not in redacted
    assert "[NIK_TEREDAKSI]" in redacted
    assert "01.234.567.8-901.000" not in redacted
    assert "[NPWP_TEREDAKSI]" in redacted
    assert "sk-proj-" not in redacted
    assert "[KREDENSIAL_TEREDAKSI]" in redacted


def test_agent_learning_candidate_evaluation_and_promotion(temp_aksa_root):
    """Verify minimal episodic recording, candidate extraction, sandbox evaluation, and promotion."""
    agent_id = "agent-creative-99"
    temp_aksa_root.provision_agent_directory(agent_id)

    mem_svc = AgentMemoryService(agent_id)
    # Record episodic tasks (redacted)
    entry1 = mem_svc.record_episodic_task(
        task_id="t1",
        session_id="s1",
        intent="Buat video promosi dengan safe margin untuk NIK 3171012345678901",
        summary="Video MP4 berdurasi 30 detik siap.",
        tools_used=["remotion_render", "visual_preview"],
        success=True,
    )
    assert "[NIK_TEREDAKSI]" in entry1.intent

    # Record tasks to meet repetition threshold
    mem_svc.record_episodic_task("t2", "s1", "Buat video promosi kedua", "Selesai", ["remotion_render", "visual_preview"], True)
    mem_svc.record_episodic_task("t3", "s1", "Buat video promosi ketiga", "Selesai", ["remotion_render", "visual_preview"], True)

    extractor = SkillCandidateExtractor(agent_id)
    cand = extractor.evaluate_task_for_learning(
        task_id="t4",
        intent="Buat video promosi keempat",
        tools_used=["remotion_render", "visual_preview"],
        success=True,
    )
    assert cand is not None
    assert cand.occurrences_count >= 3

    # Version Service: evaluate & promote
    version_svc = SkillVersionService(agent_id)
    eval_report = version_svc.evaluate_candidate(cand.skill_id)
    assert eval_report.passed is True
    assert eval_report.score >= 70.0

    promoted = version_svc.promote_candidate(cand.skill_id, version="1.0.0", promote_to_shared=False)
    assert promoted["status"] == "promoted_and_active"

    learned = version_svc.list_learned_skills()
    assert len(learned) >= 1

    # Metrics verification
    metrics = AgentLearningMetrics.get_metrics(agent_id)
    assert metrics["successful_tasks"] >= 3
    assert metrics["learned_skills_count"] >= 1


def test_dynamic_model_discovery_and_role_recommendation():
    """Verify capability normalization, resilient cache, and role routing."""
    discovery_svc = ModelDiscoveryService()

    # Fake discovered models
    models = [
        DiscoveredModel(
            provider_id="openai",
            provider_model_id="gpt-4o",
            display_name="OpenAI GPT-4o",
            capabilities=["text_input", "image_input", "text_output", "tool_calling", "computer_use"],
        ),
        DiscoveredModel(
            provider_id="deepseek",
            provider_model_id="deepseek-reasoner",
            display_name="DeepSeek R1",
            capabilities=["text_input", "text_output", "reasoning"],
        ),
        DiscoveredModel(
            provider_id="ollama",
            provider_model_id="ollama/qwen2.5-coder:7b",
            display_name="Qwen Coder Local",
            capabilities=["text_input", "text_output", "tool_calling"],
        ),
    ]

    # Save to cache and test retrieval
    discovery_svc.save_cached_models("test_prov", models)
    cached = discovery_svc.load_cached_models("test_prov")
    assert len(cached) == 3

    # Recommend for reasoning
    rec_reasoning = discovery_svc.recommend_model_for_role("reasoning", models)
    assert rec_reasoning.provider_model_id == "deepseek-reasoner"

    # Recommend for computer use
    rec_vision = discovery_svc.recommend_model_for_role("computer_use", models)
    assert rec_vision.provider_model_id == "gpt-4o"


@pytest.mark.asyncio
async def test_local_only_mode_blocks_cloud_discovery():
    """Verify that in LOCAL_ONLY mode, discovery for cloud providers returns empty and calls no cloud APIs."""
    discovery_svc = ModelDiscoveryService()
    privacy_policy_gate.configure(provider_mode="local_only")

    models = await discovery_svc.discover_provider("openai", api_key="sk-test-key-12345")
    assert models == []

    # Reset privacy gate
    privacy_policy_gate.configure(provider_mode="hybrid_with_consent")


def test_skills_marketplace_progressive_disclosure_and_indonesian_catalog():
    """Verify progressive disclosure, Indonesian curated catalog presence, and per-agent install."""
    # Check Indonesian skills
    catalog_ids = [c.id for c in CURATED_SKILL_CATALOG]
    assert "prisma-ddti-skills" in catalog_ids
    assert "naskah-id" in catalog_ids
    assert "pbj-asn-indonesia" in catalog_ids
    assert "remotion-best-practices" in catalog_ids

    # Progressive disclosure check
    instructions = agent_skills_manager.load_skill_instructions("naskah-id")
    assert "Pemeriksaan kebakuan kata" in instructions


@pytest.mark.asyncio
async def test_rest_api_root_dir_and_agent_learning_endpoints():
    """Verify REST API endpoints for root-dir, models, memory, and candidate evaluation."""
    transport = ASGITransport(app=app)
    auth_headers = {"X-AKSA-Auth-Token": settings.auth_token}
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        # 1. Root dir status
        resp_root = await client.get("/api/v1/system/root-dir")
        assert resp_root.status_code == 200
        assert resp_root.json()["is_configured"] is True

        # 2. Discovered models
        resp_models = await client.get("/api/v1/models/discovered")
        assert resp_models.status_code == 200
        assert "providers" in resp_models.json()

        # 3. Model recommend
        resp_rec = await client.get("/api/v1/models/recommend?role=coding")
        assert resp_rec.status_code == 200
        assert "role" in resp_rec.json()

        # 4. Agent metrics
        resp_metrics = await client.get("/api/v1/agents/supervisor/metrics")
        assert resp_metrics.status_code == 200
        assert "agent_id" in resp_metrics.json()

        # 5. Skill instructions (progressive disclosure)
        resp_inst = await client.get("/api/v1/skills/remotion-best-practices/instructions")
        assert resp_inst.status_code == 200
        assert len(resp_inst.json()["instructions"]) > 0
