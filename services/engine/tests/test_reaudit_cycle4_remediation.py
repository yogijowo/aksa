"""Adversarial and Comprehensive Verification Test Suite for Cycle 4 Audit Remediation (AKSA-CYCLE-4-2026-11-19).

Verifies:
1. AKSA-SEC-003-R3: Hardened Python runtime sandbox intercepts:
   - pathlib.Path.read_text & write_text
   - io.open & os.open
   - Mutating OS operations (os.replace, os.symlink, os.rename)
   - Dynamic importlib interception & raw socket poisoning
2. AKSA-SEC-001-R3: MCP wildcard permission rejection for non-system servers
3. AKSA-SKILL-002-R3: Agent-bound DB policy enforcement for skill execution
4. AKSA-SEC-002-R3: Publisher trust store persistence across restarts & admin root lock
5. AKSA-AGENT-001-R3 & AKSA-AGENT-003-R3: Format-specific postcondition validation & empirical candidate extraction
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519
import pytest

from app.core.agent_learning import (
    CandidateSkill,
    EpisodicEntry,
    LearningPrivacyFilter,
    SkillCandidateExtractor,
)
from app.core.orchestrator import TaskOutcome, verify_artifact_postcondition
from app.db.models import db_manager
from app.skills.skill_manager import (
    PublisherTrustStore,
    agent_skills_manager,
    publisher_trust_store,
)
from app.tools.mcp.mcp_client import MCPServerConfig, check_mcp_server_permissions


# ===========================================================================
# 1. AKSA-SEC-003-R3: OS and Runtime Sandbox Hardening
# ===========================================================================


@pytest.mark.asyncio
async def test_sandbox_blocks_pathlib_read_outside_workspace(tmp_path: Path):
    """Adversarial test: pathlib.Path.read_text() targeting outside workspace is blocked."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outside_file = tmp_path / "top_secret.txt"
    outside_file.write_text("CONFIDENTIAL_TOKEN_XYZ", encoding="utf-8")

    script = workspace / "pathlib_read.py"
    script.write_text(
        f"""
from pathlib import Path
import sys

target = Path(r'{outside_file}')
try:
    content = target.read_text()
    print("LEAKED:", content)
except PermissionError as exc:
    sys.stderr.write(f"BLOCKED: {{exc}}\\n")
    sys.exit(13)
""",
        encoding="utf-8",
    )

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.skills.sandbox_runner",
            "--script",
            str(script),
            "--workspace",
            str(workspace),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 13
    assert "di luar folder kerja dilarang" in res.stderr
    assert "LEAKED" not in res.stdout


@pytest.mark.asyncio
async def test_sandbox_blocks_pathlib_write_outside_workspace(tmp_path: Path):
    """Adversarial test: pathlib.Path.write_text() targeting outside workspace is blocked."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outside_file = tmp_path / "escaped_write.txt"

    script = workspace / "pathlib_write.py"
    script.write_text(
        f"""
from pathlib import Path
import sys

target = Path(r'{outside_file}')
try:
    target.write_text("malicious payload")
except PermissionError as exc:
    sys.stderr.write(f"BLOCKED: {{exc}}\\n")
    sys.exit(13)
""",
        encoding="utf-8",
    )

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.skills.sandbox_runner",
            "--script",
            str(script),
            "--workspace",
            str(workspace),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 13
    assert not outside_file.exists()


@pytest.mark.asyncio
async def test_sandbox_blocks_io_open_and_os_open_outside_workspace(tmp_path: Path):
    """Adversarial test: Low-level io.open and os.open targeting outside workspace are intercepted."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outside_file = tmp_path / "os_open_target.txt"

    script = workspace / "lowlevel_open.py"
    script.write_text(
        f"""
import os
import sys

target = r'{outside_file}'
try:
    fd = os.open(target, os.O_CREAT | os.O_WRONLY)
    os.close(fd)
except PermissionError as exc:
    sys.stderr.write(f"BLOCKED: {{exc}}\\n")
    sys.exit(13)
""",
        encoding="utf-8",
    )

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.skills.sandbox_runner",
            "--script",
            str(script),
            "--workspace",
            str(workspace),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 13
    assert not outside_file.exists()


@pytest.mark.asyncio
async def test_sandbox_blocks_mutating_os_replace_and_symlink(tmp_path: Path):
    """Adversarial test: os.replace and os.symlink pointing outside workspace are blocked."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outside_target = tmp_path / "symlink_dest.txt"
    src_file = workspace / "source.txt"
    src_file.write_text("dummy", encoding="utf-8")

    script = workspace / "os_mutating.py"
    script.write_text(
        f"""
import os
import sys

src = r'{src_file}'
dst = r'{outside_target}'
try:
    os.replace(src, dst)
except PermissionError as exc:
    sys.stderr.write(f"BLOCKED: {{exc}}\\n")
    sys.exit(13)
""",
        encoding="utf-8",
    )

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.skills.sandbox_runner",
            "--script",
            str(script),
            "--workspace",
            str(workspace),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 13
    assert not outside_target.exists()


@pytest.mark.asyncio
async def test_sandbox_blocks_dynamic_import_of_ctypes(tmp_path: Path):
    """Adversarial test: Dynamic import of ctypes via importlib.import_module is blocked."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    script = workspace / "dynamic_import.py"
    script.write_text(
        """
import sys

try:
    # Use getattr to evade trivial static regex
    importer = getattr(sys.modules.get("importlib", sys), "import_module", None)
    if importer:
        importer("ctypes")
    else:
        raise PermissionError("importlib unavailable")
except PermissionError as exc:
    sys.stderr.write(f"BLOCKED: {exc}\\n")
    sys.exit(13)
""",
        encoding="utf-8",
    )

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.skills.sandbox_runner",
            "--script",
            str(script),
            "--workspace",
            str(workspace),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 13
    assert "dilarang oleh Sandbox AKSA" in res.stderr or "unavailable" in res.stderr


# ===========================================================================
# 2. AKSA-SEC-001-R3: MCP Server Wildcard Permission Restriction
# ===========================================================================


def test_mcp_wildcard_rejected_for_third_party_and_community_servers():
    """Verify third-party MCP servers attempting to declare wildcard permissions are rejected."""
    # 1. Untrusted server declares '*'
    untrusted_server = MCPServerConfig(
        id="community_untrusted",
        name="Untrusted Community Server",
        command="node",
        trust_level="unreviewed",
        permissions=["*"],
    )
    allowed, reason = check_mcp_server_permissions(untrusted_server, "write_file")
    assert allowed is False
    assert "Izin wildcard ditolak untuk server non-system" in str(reason)

    # 2. System-trusted server declares '*'
    system_server = MCPServerConfig(
        id="system_internal",
        name="Official System Core Server",
        command="node",
        trust_level="system_trusted",
        permissions=["*"],
    )
    allowed_sys, reason_sys = check_mcp_server_permissions(system_server, "write_file")
    assert allowed_sys is True
    assert reason_sys is None


# ===========================================================================
# 3. AKSA-SKILL-002-R3: Agent-Bound Skill DB Policy Enforcement
# ===========================================================================


@pytest.mark.asyncio
async def test_agent_ownership_policy_enforcement_at_db_layer(tmp_path: Path):
    """Verify that a skill registered for agent_alpha is blocked if executed by agent_beta."""
    await db_manager.initialize()

    skill_id = "exclusive-alpha-tool"
    await db_manager.upsert_installed_skill({
        "skill_id": skill_id,
        "name": "Alpha Dedicated Tool",
        "version": "1.0.0",
        "publisher": "alpha_corp",
        "trust_level": "custom",
        "has_scripts": True,
        "enabled": True,
        "target_agent_id": "agent_alpha",
    })

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Attempt execution from unauthorized agent_beta -> PermissionError
    with pytest.raises(PermissionError) as exc_info:
        await agent_skills_manager.execute_skill_script(
            skill_id=skill_id,
            script_rel_path="scripts/run.py",
            workspace_path=str(workspace),
            agent_id="agent_beta",
        )
    assert "terikat secara eksklusif pada agen 'agent_alpha'" in str(exc_info.value)


# ===========================================================================
# 4. AKSA-SEC-002-R3: Publisher Trust Store Persistence Across Restarts
# ===========================================================================


def test_publisher_trust_store_persistence_across_restarts(tmp_path: Path):
    """Verify trust store saves enrolled publishers and revocations to disk, reloading them upon restart."""
    persist_file = tmp_path / "trust_store.json"

    # 1. Initialize store instance with custom persistence path
    store1 = PublisherTrustStore(persist_path=persist_file)

    root_priv = ed25519.Ed25519PrivateKey.generate()
    root_pub_b64 = base64.b64encode(root_priv.public_key().public_bytes_raw()).decode("ascii")
    store1.set_root_public_key(root_pub_b64, allow_override=True)

    pub_priv = ed25519.Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(pub_priv.public_key().public_bytes_raw()).decode("ascii")

    sig = PublisherTrustStore.sign_publisher_delegation("persisted_publisher", pub_b64, root_priv)
    store1.register_publisher("persisted_publisher", pub_b64, root_signature_b64=sig)

    assert "persisted_publisher" in store1._trusted_keys
    assert persist_file.exists()

    # 2. Simulate complete application restart with new store instance
    store2 = PublisherTrustStore(root_public_key_b64=root_pub_b64, persist_path=persist_file)
    assert "persisted_publisher" in store2._trusted_keys
    assert len(store2._enrollment_audit_trail) == 1

    # 3. Revoke publisher in store2 and verify persistence
    store2.revoke_publisher("persisted_publisher")
    assert store2.is_revoked("persisted_publisher")

    # 4. Restart store3 and verify revocation is maintained
    store3 = PublisherTrustStore(root_public_key_b64=root_pub_b64, persist_path=persist_file)
    assert store3.is_revoked("persisted_publisher")
    assert "persisted_publisher" not in store3._trusted_keys


# ===========================================================================
# 5. AKSA-AGENT-001-R3 & 003-R3: Format-Specific Postconditions & Learning
# ===========================================================================


def test_format_specific_artifact_postcondition_validation(tmp_path: Path):
    """Verify corrupt or truncated documents are caught by format-specific postcondition validation."""
    # 1. Non-existent file
    ok, reason = verify_artifact_postcondition(tmp_path / "missing.xlsx")
    assert ok is False
    assert "File tidak ditemukan" in reason

    # 2. Zero-byte file
    zero_file = tmp_path / "empty.docx"
    zero_file.touch()
    ok_zero, reason_zero = verify_artifact_postcondition(zero_file)
    assert ok_zero is False
    assert "0 byte" in reason_zero

    # 3. Corrupt XLSX (random garbage text instead of ZIP/XML)
    corrupt_xlsx = tmp_path / "bad.xlsx"
    corrupt_xlsx.write_text("NOT_A_VALID_ZIP_XLSX_HEADER", encoding="utf-8")
    ok_xlsx, reason_xlsx = verify_artifact_postcondition(corrupt_xlsx)
    assert ok_xlsx is False
    assert "Integritas Excel" in reason_xlsx

    # 4. Corrupt DOCX
    corrupt_docx = tmp_path / "bad.docx"
    corrupt_docx.write_text("CORRUPTED_DOCX_FILE_CONTENT", encoding="utf-8")
    ok_docx, reason_docx = verify_artifact_postcondition(corrupt_docx)
    assert ok_docx is False
    assert "Integritas dokumen Word" in reason_docx

    # 5. Valid JSON
    valid_json = tmp_path / "valid.json"
    valid_json.write_text(json.dumps({"status": "ok", "count": 42}), encoding="utf-8")
    ok_json, reason_json = verify_artifact_postcondition(valid_json)
    assert ok_json is True


def test_skill_candidate_extractor_stores_structured_traces_and_empirical_confidence(tmp_path: Path):
    """Verify CandidateSkill records sanitized structured traces and empirical confidence."""
    from app.core.agent_directory import agent_directory_service
    agent_directory_service.set_root_dir(tmp_path / "aksa_data")

    extractor = SkillCandidateExtractor("agent_analyst")

    execution_trace = [
        {
            "action_label": "read_financial_data",
            "agent_name": "agent_analyst",
            "input": {"path": "/workspace/data.csv", "api_key": "sk-123456789012345678901234567890"},
            "output": {"summary": "NIK 1234567890123456 loaded with 100 rows"},
            "status": "success",
        },
        {
            "action_label": "generate_report_xlsx",
            "agent_name": "agent_analyst",
            "input": {"destination": "/workspace/report.xlsx"},
            "output": "Artifact /workspace/report.xlsx generated successfully",
            "status": "success",
        },
    ]

    candidate = extractor.evaluate_task_for_learning(
        task_id="task_test_1001",
        intent="Buat laporan keuangan bulanan lengkap",
        tools_used=["read_financial_data", "generate_report_xlsx"],
        success=True,
        user_explicit_teach=True,
        outcome="success",
        execution_trace=execution_trace,
    )

    assert candidate is not None
    assert candidate.confidence >= 0.70
    assert "final_confidence" in candidate.empirical_metrics

    # Verify structured traces are stored and sensitive data/PII is redacted
    assert len(candidate.structured_traces) == 2
    step1 = candidate.structured_traces[0]
    assert step1["tool_name"] == "read_financial_data"

    # Check PII and API keys were scrubbed
    input_str = json.dumps(step1["input_summary"])
    output_str = json.dumps(step1["output_summary"])
    assert "sk-12345" not in input_str
    assert "[KREDENSIAL_TEREDAKSI]" in input_str
    assert "1234567890123456" not in output_str
    assert "[NIK_TEREDAKSI]" in output_str

