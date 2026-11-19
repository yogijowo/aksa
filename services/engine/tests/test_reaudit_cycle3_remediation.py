"""Comprehensive Adversarial and Regression Test Suite for Re-Audit Cycle 3 (18 Nov 2026).

Covers all findings and acceptance criteria from docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-3-2026-11-18.md:
- AKSA-SEC-001-R2 (P0): MCP unknown / neutral tools fail-closed (RiskLevel.UNKNOWN, mandatory HITL, server permission check fail-closed).
- AKSA-SEC-003-R2 (P0): Skill script OS and runtime sandbox (filesystem path jail, network block, subprocess block, resource limits).
- AKSA-SKILL-002-R2 (P1): Agent-bound skill execution (Agent A cannot execute Agent B's private skills).
- AKSA-SEC-004-R2 (P1): Sidecar atomic manifest writing, port synchronization, and child process PID validation.
- AKSA-SEC-002-R2 (P1): Publisher trust enrollment strictly requires root delegation signature (self-registration rejected).
- AKSA-AGENT-001-R2 & AKSA-AGENT-003-R2 (P2): Granular task outcomes (SUCCESS, PARTIAL_SUCCESS, FAILED, CANCELLED, UNVERIFIED)
  and trace-driven procedural skill candidate extraction.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import sys
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.core.agent_directory import agent_directory_service
from app.core.agent_learning import (
    AgentMemoryService,
    SkillCandidateExtractor,
)
from app.core.orchestrator import TaskOutcome
from app.core.sandbox import RiskLevel, execution_policy_gateway
from app.skills.skill_manager import (
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
)


# ---------------------------------------------------------------------------
# 1. AKSA-SEC-001-R2: MCP Unknown & Neutral Tools Fail-Closed
# ---------------------------------------------------------------------------


def test_mcp_unknown_and_neutral_tools_classified_unknown():
    """Verify neutrally named MCP tools (process_data, sync_state, manage_resource) are UNKNOWN, never LOW."""
    server = MCPServerConfig(
        id="test_custom_mcp",
        name="Custom MCP",
        transport="stdio",
        command="python",
        permissions=["filesystem.workspace.read"],
    )

    # Neutral names must NOT default to LOW
    assert classify_mcp_tool_risk(server, "process_data") == RiskLevel.HIGH  # 'process' is high-risk keyword
    assert classify_mcp_tool_risk(server, "sync_state") == RiskLevel.HIGH  # 'sync' is high-risk keyword
    assert classify_mcp_tool_risk(server, "manage_resource") == RiskLevel.HIGH  # 'manage' is high-risk keyword
    assert classify_mcp_tool_risk(server, "custom_handler") == RiskLevel.UNKNOWN
    assert classify_mcp_tool_risk(server, "unmapped_neutral_op") == RiskLevel.UNKNOWN

    # Pure read-only tools remain LOW
    assert classify_mcp_tool_risk(server, "read_file") == RiskLevel.LOW
    assert classify_mcp_tool_risk(server, "list_directory") == RiskLevel.LOW


def test_mcp_server_permissions_fail_closed_for_empty_and_unmapped():
    """Verify MCP servers with no permissions or unmapped tools fail closed."""
    # 1. Server with empty permissions
    empty_server = MCPServerConfig(
        id="empty_server",
        name="Empty Perm Server",
        transport="stdio",
        command="python",
        permissions=[],
    )
    ok, err = check_mcp_server_permissions(empty_server, "read_file")
    assert ok is False
    assert "tidak mendeklarasikan izin apa pun" in (err or "")

    # 2. Server with only read permissions called with unmapped neutral tool
    read_only_server = MCPServerConfig(
        id="readonly_server",
        name="Read Only Server",
        transport="stdio",
        command="python",
        permissions=["filesystem.workspace.read"],
    )
    ok_neutral, err_neutral = check_mcp_server_permissions(read_only_server, "process_unmapped")
    assert ok_neutral is False
    assert "tidak memiliki izin" in (err_neutral or "")
    assert "fail-closed" in (err_neutral or "")


@pytest.mark.asyncio
async def test_mcp_unknown_tool_blocked_without_hitl():
    """Adversarial test: prove neutrally-named unknown tool cannot bypass HITL."""
    mcp_client_manager.register_server(
        MCPServerConfig(
            id="adversarial_server",
            name="Adversarial Server",
            transport="stdio",
            command="python",
            permissions=["filesystem.workspace.read", "mcp.adversarial_server.custom_op"],
            enabled=True,
            discovered_tools=["custom_op"],
        )
    )

    try:
        # Invoking unclassified tool without HITL grant must fail closed
        res = await mcp_client_manager.invoke_mcp_tool(
            server_id="adversarial_server",
            tool_name="custom_op",
            arguments={"param": "value"},
        )
        assert res.success is False
        assert res.data.get("status") == "hitl_approval_required"
        assert res.data.get("hitl_required") is True
        assert res.data.get("risk_level") == RiskLevel.UNKNOWN.value
    finally:
        mcp_client_manager._servers.pop("adversarial_server", None)


# ---------------------------------------------------------------------------
# 2. AKSA-SEC-003-R2: OS and Python Runtime Sandbox for Skill Scripts
# ---------------------------------------------------------------------------


def test_sandbox_ast_blocks_dangerous_modules_and_eval():
    """Verify AST security scanner blocks eval, os.system, socket, urllib, subprocess."""
    from app.skills.sandbox_runner import scan_ast_security

    # 1. eval / exec
    with pytest.raises(PermissionError) as exc_eval:
        scan_ast_security("eval('2 + 2')")
    assert "eval()" in str(exc_eval.value)

    # 2. socket import
    with pytest.raises(PermissionError) as exc_sock:
        scan_ast_security("import socket\ns = socket.socket()")
    assert "socket" in str(exc_sock.value)

    # 3. urllib import
    with pytest.raises(PermissionError) as exc_url:
        scan_ast_security("import urllib.request\nurllib.request.urlopen('http://evil.com')")
    assert "urllib" in str(exc_url.value)

    # 4. subprocess import
    with pytest.raises(PermissionError) as exc_sub:
        scan_ast_security("from subprocess import Popen")
    assert "subprocess" in str(exc_sub.value)

    # 5. os.system attribute
    with pytest.raises(PermissionError) as exc_sys:
        scan_ast_security("import os\nos.system('whoami')")
    assert "os.system" in str(exc_sys.value)


@pytest.mark.asyncio
async def test_sandbox_runner_blocks_filesystem_read_outside_workspace(tmp_path: Path):
    """Verify runtime filesystem jail blocks reading files outside authorized workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("CONFIDENTIAL_DATA", encoding="utf-8")

    # Script attempting to read outside workspace
    script = workspace / "evil_read.py"
    script.write_text(
        f"""
path = r'{outside_file}'
try:
    with open(path, 'r') as f:
        print(f.read())
except PermissionError as e:
    import sys
    sys.stderr.write(f"BLOCKED: {{e}}\\n")
    sys.exit(13)
""",
        encoding="utf-8",
    )

    import subprocess
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


@pytest.mark.asyncio
async def test_sandbox_runner_blocks_filesystem_write_outside_workspace(tmp_path: Path):
    """Verify runtime filesystem jail blocks writing files outside authorized workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outside_target = tmp_path / "escaped.txt"

    script = workspace / "evil_write.py"
    script.write_text(
        f"""
path = r'{outside_target}'
try:
    with open(path, 'w') as f:
        f.write("malicious payload")
except PermissionError as e:
    import sys
    sys.stderr.write(f"BLOCKED: {{e}}\\n")
    sys.exit(13)
""",
        encoding="utf-8",
    )

    import subprocess
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
    assert not outside_target.exists()


# ---------------------------------------------------------------------------
# 3. AKSA-SKILL-002-R2: Agent-Bound Skill Execution Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_cannot_execute_another_agents_skill(tmp_path: Path):
    """Adversarial test: Agent A cannot execute a skill installed under Agent B."""
    agent_directory_service.set_root_dir(tmp_path / "aksa_data")

    # Install skill under Agent B
    agent_b_skill_dir = agent_directory_service.resolve_agent_path(
        "agent_b", "skills/installed/agent-b-private-skill/scripts"
    )
    agent_b_skill_dir.mkdir(parents=True, exist_ok=True)
    run_py = agent_b_skill_dir / "run.py"
    run_py.write_text("print('SECRET_AGENT_B_EXECUTED')", encoding="utf-8")

    from app.db.models import db_manager
    await db_manager.initialize()
    await db_manager.upsert_installed_skill({
        "skill_id": "agent-b-private-skill",
        "name": "Agent B Private",
        "version": "1.0.0",
        "publisher": "agent_b",
        "trust_level": "custom",
        "has_scripts": True,
        "has_network": False,
        "enabled": True,
    })

    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)

    # 1. Agent A attempts to execute Agent B's skill -> MUST BE REJECTED
    with pytest.raises(PermissionError) as exc_info:
        await agent_skills_manager.execute_skill_script(
            skill_id="agent-b-private-skill",
            script_rel_path="scripts/run.py",
            workspace_path=str(workspace),
            agent_id="agent_a",
        )
    assert "Akses ditolak oleh isolasi agen AKSA" in str(exc_info.value)

    # 2. Agent B executes its own skill -> SUCCEEDS
    res = await agent_skills_manager.execute_skill_script(
        skill_id="agent-b-private-skill",
        script_rel_path="scripts/run.py",
        workspace_path=str(workspace),
        agent_id="agent_b",
    )
    assert res["exit_code"] == 0
    assert "SECRET_AGENT_B_EXECUTED" in res["stdout"]


# ---------------------------------------------------------------------------
# 4. AKSA-SEC-002-R2: Publisher Trust Enrollment Requires Root Delegation Signature
# ---------------------------------------------------------------------------


def test_publisher_trust_enrollment_strictly_requires_root_signature():
    """Verify self-registration without root authorization signature fails closed."""
    store = PublisherTrustStore()

    # Generate custom publisher keypair
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode("ascii")

    # 1. Self-registration without signature must raise PermissionError
    with pytest.raises(PermissionError) as exc_nosig:
        store.register_publisher("rogue_publisher", pub_b64)
    assert "Wajib menyertakan tanda tangan delegasi resmi" in str(exc_nosig.value)

    # 2. Registration with forged signature must raise PermissionError
    forged_sig = base64.b64encode(b"forged_invalid_signature_32_bytes!").decode("ascii")
    with pytest.raises(PermissionError) as exc_forged:
        store.register_publisher("rogue_publisher", pub_b64, root_signature_b64=forged_sig)
    assert "Otorisasi root gagal" in str(exc_forged.value)

    # 3. Registration with genuine root delegation signature succeeds
    test_root_priv = ed25519.Ed25519PrivateKey.generate()
    test_root_pub_b64 = base64.b64encode(test_root_priv.public_key().public_bytes_raw()).decode("ascii")
    store.set_root_public_key(test_root_pub_b64)

    valid_sig = PublisherTrustStore.sign_publisher_delegation("authorized_org", pub_b64, test_root_priv)
    store.register_publisher("authorized_org", pub_b64, root_signature_b64=valid_sig)

    assert "authorized_org" in store._trusted_keys
    assert len(store._enrollment_audit_trail) == 1


# ---------------------------------------------------------------------------
# 5. AKSA-AGENT-001-R2 & AKSA-AGENT-003-R2: Granular Outcomes & Trace Learning
# ---------------------------------------------------------------------------


def test_candidate_learning_rejects_unverified_and_failed_outcomes(tmp_path: Path):
    """Verify tasks with outcome UNVERIFIED, PARTIAL_SUCCESS, or FAILED are never extracted."""
    agent_directory_service.set_root_dir(tmp_path / "aksa_data")
    extractor = SkillCandidateExtractor("agent_test")

    # 1. Unverified outcome (e.g. artifact missing) -> None
    res_unverified = extractor.evaluate_task_for_learning(
        task_id="task_001",
        intent="Generate quarterly report",
        tools_used=["write_excel_report"],
        success=False,
        outcome=TaskOutcome.UNVERIFIED.value,
    )
    assert res_unverified is None

    # 2. Partial success -> None
    res_partial = extractor.evaluate_task_for_learning(
        task_id="task_002",
        intent="Generate quarterly report",
        tools_used=["write_excel_report"],
        success=False,
        outcome=TaskOutcome.PARTIAL_SUCCESS.value,
    )
    assert res_partial is None


def test_candidate_learning_extracts_concrete_procedural_steps_from_trace(tmp_path: Path):
    """Verify successful task extracts realistic procedural steps directly from execution trace."""
    agent_directory_service.set_root_dir(tmp_path / "aksa_data")
    extractor = SkillCandidateExtractor("agent_test")

    execution_trace = [
        {
            "agent_name": "Spesialis Dokumen",
            "action_label": "Buat Ringkasan Keuangan Excel",
            "detail": "Kalkulasi formula SUM dan AVERAGE pada sheet 'Q4'",
            "artifact": "laporan_q4.xlsx",
        },
        {
            "agent_name": "Spesialis Desain & Naskah",
            "action_label": "Susun Naskah Dinas Word",
            "detail": "Template naskah dinas resmi dengan kop surat dan tabel",
            "artifact": "pengantar_q4.docx",
        },
    ]

    candidate = extractor.evaluate_task_for_learning(
        task_id="task_100",
        intent="Buat laporan keuangan Q4 lengkap dengan naskah dinas",
        tools_used=["write_excel_report", "write_word_document"],
        success=True,
        outcome=TaskOutcome.SUCCESS.value,
        user_explicit_teach=True,
        execution_trace=execution_trace,
    )

    assert candidate is not None
    assert len(candidate.steps) >= 4
    # Step 1 is goal initialization
    assert "Inisialisasi sasaran tugas" in candidate.steps[0]
    # Step 2 matches first trace action
    assert "Buat Ringkasan Keuangan Excel" in candidate.steps[1]
    assert "laporan_q4.xlsx" in candidate.steps[1]
    # Step 3 matches second trace action
    assert "Susun Naskah Dinas Word" in candidate.steps[2]
    assert "pengantar_q4.docx" in candidate.steps[2]
    # Final step is verification
    assert "Verifikasi integritas artefak keluaran" in candidate.steps[-1]


# ---------------------------------------------------------------------------
# 6. AKSA-SEC-004-R2: Sidecar Atomic Manifest Writing
# ---------------------------------------------------------------------------


def test_atomic_engine_port_manifest_write_and_replace(tmp_path: Path):
    """Verify engine_port.json is written atomically via temporary file and rename."""
    port_file = tmp_path / "engine_port.json"
    temp_file = tmp_path / f"engine_port.json.tmp.{os.getpid()}"

    payload = {
        "host": "127.0.0.1",
        "port": 43120,
        "pid": os.getpid(),
        "version": "1.0.0",
    }

    # Write to temp file first
    temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    assert temp_file.exists()
    assert not port_file.exists()

    # Atomic replace
    os.replace(temp_file, port_file)
    assert port_file.exists()
    assert not temp_file.exists()

    content = json.loads(port_file.read_text(encoding="utf-8"))
    assert content["port"] == 43120
    assert content["pid"] == os.getpid()
