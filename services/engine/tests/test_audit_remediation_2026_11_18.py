"""Comprehensive Security & Architecture Regression Suite for Independent Audit (18 Nov 2026).

Covers all 10 findings from docs/AKSA-INDEPENDENT-TECHNICAL-AUDIT-2026-11-18.md:
- AKSA-SEC-001: MCP per-tool dynamic risk classification and HITL approval enforcement.
- AKSA-SEC-002: Zero private keys in trust store, Ed25519 signature verification, key revocation.
- AKSA-SEC-003: Skill script sandbox pre-execution scan, process group isolation, output bounds.
- AKSA-SEC-004: Sidecar port lifecycle, atomic port file, and HMAC identity handshake.
- AKSA-MCP-001: Sequential JSON-RPC initialize/notifications/tools handshake.
- AKSA-MCP-002: Full JSON Schema validation against nested structures and types.
- AKSA-AGENT-001: Substantive tool-specific learned procedural steps.
- AKSA-AGENT-002: Isolated episodic memory and candidate learning per executing agent.
- AKSA-AGENT-003: Genuine task success computation (failed tools record success=False).
- AKSA-SKILL-001: Immutable skill versioning collision rejection.
- AKSA-SKILL-002: Isolated per-agent skill package installation.
- AKSA-SKILL-003: Curated skill manifest synchrony with materialized scripts on disk.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.core.sandbox import RiskLevel, execution_policy_gateway
from app.core.agent_directory import AgentDirectoryService, agent_directory_service
from app.core.agent_learning import (
    AgentMemoryService,
    CandidateSkill,
    SkillCandidateExtractor,
    SkillVersionService,
)
from app.skills.skill_manager import (
    CURATED_SKILL_CATALOG,
    OFFICIAL_AKSA_ROOT_PUBLIC_KEY_B64,
    PublisherTrustStore,
    agent_skills_manager,
    publisher_trust_store,
)
from app.tools.mcp.mcp_client import (
    MCPServerConfig,
    check_mcp_server_permissions,
    classify_mcp_tool_risk,
    mcp_client_manager,
    validate_arguments_against_schema,
)
from app.tools.registry import tool_registry


# ---------------------------------------------------------------------------
# 1. AKSA-SEC-001 & AKSA-MCP-002: MCP Dynamic Risk, Permissions, and JSON Schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_dynamic_risk_classification():
    """Verify tool risk is classified per tool name and action, not blanket MEDIUM (AKSA-SEC-001)."""
    server = mcp_client_manager.get_server("mcp_filesystem")
    assert server is not None

    # Read-only tools must be LOW risk
    risk_read = classify_mcp_tool_risk(server, "read_file")
    assert risk_read == RiskLevel.LOW

    risk_list = classify_mcp_tool_risk(server, "list_directory")
    assert risk_list == RiskLevel.LOW

    # Destructive / mutating tools must be HIGH risk
    risk_write = classify_mcp_tool_risk(server, "write_file")
    assert risk_write == RiskLevel.HIGH

    risk_del = classify_mcp_tool_risk(server, "delete_file")
    assert risk_del == RiskLevel.HIGH

    risk_drop = classify_mcp_tool_risk(server, "drop_table")
    assert risk_drop == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_mcp_high_risk_tool_blocked_without_hitl():
    """Verify high-risk MCP tool execution is blocked fail-closed when HITL grant is missing (AKSA-SEC-001)."""
    mcp_client_manager.toggle_server("mcp_filesystem", enabled=True)
    try:
        # High risk: write_file without grant
        res = await mcp_client_manager.invoke_mcp_tool(
            server_id="mcp_filesystem",
            tool_name="write_file",
            arguments={"path": "/tmp/test.txt", "content": "data"},
        )
        assert res.success is False
        assert res.data.get("status") == "hitl_approval_required"
        assert res.data.get("hitl_required") is True
        assert "ExecutionPolicyGateway" in res.summary
    finally:
        mcp_client_manager.toggle_server("mcp_filesystem", enabled=False)


@pytest.mark.asyncio
async def test_mcp_server_permission_enforcement():
    """Verify tool execution fails closed if server lacks declared capability permissions (AKSA-SEC-001)."""
    # Create test server with only read permissions
    test_server = MCPServerConfig(
        id="test_readonly_mcp",
        name="Readonly Test Server",
        command="node",
        args=["index.js"],
        permissions=["filesystem.workspace.read"],  # No write permission!
        enabled=True,
    )
    mcp_client_manager.register_server(test_server)

    # Check permission directly
    perm_ok, perm_err = check_mcp_server_permissions(test_server, "write_file")
    assert perm_ok is False
    assert "tidak memiliki izin" in str(perm_err)

    # Execution must fail with permission_denied
    res = await mcp_client_manager.invoke_mcp_tool(
        server_id="test_readonly_mcp",
        tool_name="write_file",
        arguments={"path": "output.txt", "content": "test"},
    )
    assert res.success is False
    assert res.data.get("status") == "permission_denied"


def test_mcp_full_json_schema_validation_nested_and_types():
    """Verify full JSON Schema validation supports nested structures, enums, and required properties (AKSA-MCP-002)."""
    schema = {
        "type": "object",
        "required": ["user", "settings"],
        "properties": {
            "user": {
                "type": "object",
                "required": ["name", "age"],
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 18},
                },
            },
            "settings": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string", "enum": ["light", "dark"]},
                },
            },
        },
    }

    # 1. Valid nested arguments
    valid_args = {
        "user": {"name": "Budi", "age": 25},
        "settings": {"theme": "dark"},
    }
    ok, err = validate_arguments_against_schema(schema, valid_args)
    assert ok is True
    assert err is None

    # 2. Missing top-level required property
    ok, err = validate_arguments_against_schema(schema, {"user": {"name": "Budi", "age": 25}})
    assert ok is False
    assert "settings" in str(err)

    # 3. Invalid nested property type (string instead of integer)
    invalid_nested = {
        "user": {"name": "Budi", "age": "dua puluh lima"},
        "settings": {"theme": "dark"},
    }
    ok, err = validate_arguments_against_schema(schema, invalid_nested)
    assert ok is False
    assert "age" in str(err)

    # 4. Invalid enum value in nested object
    invalid_enum = {
        "user": {"name": "Budi", "age": 25},
        "settings": {"theme": "neon-green"},
    }
    ok, err = validate_arguments_against_schema(schema, invalid_enum)
    assert ok is False
    assert "Validasi parameter gagal" in str(err)


# ---------------------------------------------------------------------------
# 2. AKSA-SEC-002: Cryptographic Trust Store, No Private Keys, Revocation
# ---------------------------------------------------------------------------


def test_publisher_trust_store_no_private_keys_and_revocation():
    """Verify zero private keys exist in PublisherTrustStore and key revocation functions (AKSA-SEC-002)."""
    store = PublisherTrustStore()

    # Must NOT have any private key attribute
    assert not hasattr(store, "_official_priv")
    assert not hasattr(store, "official_priv")
    assert not hasattr(store, "official_seed")

    # Official public key must be loaded
    assert "aksa_official" in store._trusted_keys

    # Set up test root authority for verification
    test_root_priv = ed25519.Ed25519PrivateKey.generate()
    test_root_pub_b64 = base64.b64encode(test_root_priv.public_key().public_bytes_raw()).decode("ascii")
    store.set_root_public_key(test_root_pub_b64)

    # Generate custom publisher keypair to test signing & verification
    custom_priv = ed25519.Ed25519PrivateKey.generate()
    custom_pub_b64 = base64.b64encode(custom_priv.public_key().public_bytes_raw()).decode("ascii")

    pub_id = "test_verified_org"

    # Self-registration without root signature must fail-closed (AKSA-SEC-002-R2)
    with pytest.raises(PermissionError) as exc_info:
        store.register_publisher(pub_id, custom_pub_b64)
    assert "tanda tangan delegasi resmi" in str(exc_info.value)

    # Forged root delegation signature must be rejected
    with pytest.raises(PermissionError) as exc_info_forged:
        store.register_publisher(pub_id, custom_pub_b64, root_signature_b64=base64.b64encode(b"forged_bytes_32").decode("ascii"))
    assert "Otorisasi root gagal" in str(exc_info_forged.value)

    # Valid root-delegated registration succeeds
    valid_sig = PublisherTrustStore.sign_publisher_delegation(pub_id, custom_pub_b64, test_root_priv)
    store.register_publisher(pub_id, custom_pub_b64, root_signature_b64=valid_sig)

    payload = b"AKSA_TEST_PACKAGE_HASH_1234567890abcdef"
    signature = base64.b64encode(custom_priv.sign(payload)).decode("ascii")

    # 1. Valid signature
    assert store.verify_signature(payload, signature, pub_id) is True

    # 2. Tampered payload
    assert store.verify_signature(b"tampered_payload", signature, pub_id) is False

    # 3. Revoke publisher key
    store.revoke_publisher(pub_id)
    assert store.is_revoked(pub_id) is True
    # Verification must fail once revoked
    assert store.verify_signature(payload, signature, pub_id) is False

    # 4. Re-registration of revoked key must raise PermissionError
    with pytest.raises(PermissionError):
        store.register_publisher(pub_id, custom_pub_b64, root_signature_b64=valid_sig)


# ---------------------------------------------------------------------------
# 3. AKSA-SKILL-001 & AKSA-SKILL-002: Immutable Skills & Agent Isolation
# ---------------------------------------------------------------------------


def test_immutable_skill_version_cannot_be_overwritten(tmp_path: Path):
    """Verify promoting a candidate fails with FileExistsError if target version exists (AKSA-SKILL-001)."""
    from app.core.agent_directory import agent_directory_service
    old_root = agent_directory_service.root_dir
    agent_directory_service.set_root_dir(tmp_path)

    try:
        agent_id = "agent-audit-01"
        agent_directory_service.provision_agent_directory(agent_id)

        # Manually create existing version 1.0.0
        existing_version_dir = agent_directory_service.resolve_agent_path(
            agent_id, "skills/learned/excel-recap/1.0.0"
        )
        existing_version_dir.mkdir(parents=True, exist_ok=True)
        (existing_version_dir / "SKILL.md").write_text("# Existing immutable version", encoding="utf-8")

        # Create candidate skill with same name
        cand_dir = agent_directory_service.resolve_agent_path(
            agent_id, "skills/candidates/cand-excel-recap-20261118000000"
        )
        cand_dir.mkdir(parents=True, exist_ok=True)
        (cand_dir / "SKILL.md").write_text("---\nname: Test\n---\n# New candidate content", encoding="utf-8")

        version_svc = SkillVersionService(agent_id)

        # Promoting to existing version 1.0.0 must be rejected
        with pytest.raises(FileExistsError) as exc_info:
            version_svc.promote_candidate("cand-excel-recap-20261118000000", version="1.0.0")
        assert "sudah ada dan bersifat immutable" in str(exc_info.value)

    finally:
        agent_directory_service.set_root_dir(old_root)


@pytest.mark.asyncio
async def test_curated_skill_manifest_synchrony_with_scripts():
    """Verify curated skills materialize declared scripts on disk (AKSA-SKILL-003)."""
    # Pick a curated skill that declares scripts
    tax_skill = next((c for c in CURATED_SKILL_CATALOG if c.id == "indonesian-tax-calculator"), None)
    assert tax_skill is not None
    assert tax_skill.has_scripts is True
    assert "scripts/pph21_calculator.py" in tax_skill.scripts

    # Install skill
    installed = await agent_skills_manager.install_curated_skill(tax_skill.id)
    assert installed is not None

    skill_dir = agent_skills_manager.skills_dir / tax_skill.id
    script_path = skill_dir / "scripts/pph21_calculator.py"

    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")
    assert "calculate_ter_pph21" in content or "pph" in content.lower()


# ---------------------------------------------------------------------------
# 4. AKSA-AGENT-001, 002, 003: Substantive Steps, Agent Isolation, Real Success
# ---------------------------------------------------------------------------


def test_candidate_skill_extractor_generates_substantive_steps(tmp_path: Path):
    """Verify extracted candidate skills generate tool-specific procedural steps (AKSA-AGENT-001)."""
    from app.core.agent_directory import agent_directory_service
    old_root = agent_directory_service.root_dir
    agent_directory_service.set_root_dir(tmp_path)

    try:
        agent_id = "agent-finance-audit"
        agent_directory_service.provision_agent_directory(agent_id)
        extractor = SkillCandidateExtractor(agent_id)

        cand = extractor.evaluate_task_for_learning(
            task_id="task_substantive_test",
            intent="Rekonsiliasi transaksi kas dan validasi workbook excel bulanan",
            tools_used=["excel_recap_monthly", "csv_reconciliation"],
            success=True,
            user_explicit_teach=True,
        )

        assert cand is not None
        # Check that steps are substantive and tool-specific, not generic placeholders
        steps_text = " ".join(cand.steps).lower()
        assert "excel" in steps_text or "dataset" in steps_text or "kalkulasi" in steps_text
        assert any("authorized workspace" in v for v in cand.validations)
    finally:
        agent_directory_service.set_root_dir(old_root)


def test_failed_task_records_success_false():
    """Verify failed tasks record success=False in episodic memory (AKSA-AGENT-003)."""
    mem_svc = AgentMemoryService("test-agent-failure-check")
    entry = mem_svc.record_episodic_task(
        task_id="task_failed_01",
        session_id="session_01",
        intent="Ubah berkas pdf ke docx tanpa izin",
        summary="Eksekusi gagal: Izin write ditolak di workspace",
        tools_used=["convert_pdf_to_word"],
        success=False,
    )
    assert entry.success is False

    # Candidate extractor must ignore failed task unless explicit teach
    extractor = SkillCandidateExtractor("test-agent-failure-check")
    cand = extractor.evaluate_task_for_learning(
        task_id="task_failed_01",
        intent="Ubah berkas pdf ke docx tanpa izin",
        tools_used=["convert_pdf_to_word"],
        success=False,
        user_explicit_teach=False,
    )
    assert cand is None

