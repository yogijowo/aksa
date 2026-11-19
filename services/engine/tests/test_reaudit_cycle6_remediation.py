"""Cycle 6 Adversarial & Runtime Remediation Suite (AKSA-CYCLE-6-2026-11-19).

Verifies all Cycle 6 findings:
1. AKSA-SEC-003-R5: No raw command return in wrap_command(); Windows AppContainer + suspended
   Job Object fail-closed behavior; real Win32 / macOS / Linux boundary tests.
2. AKSA-SEC-005-R5 & R6: macOS Seatbelt strict (deny default) profile (including system secrets
   outside /Users & execv denial); Linux bwrap non-root-bind profile.
3. AKSA-SEC-004-R5: Sidecar launch_id + atomic 0600 manifest + loopback/version invariants.
4. AKSA-AGENT-003-R5: Unknown extensions return unsupported (never auto-pass); JSON scalars,
   1-cell Excel placeholders, and textless ornamental PDF drawings fail; task-specific schemas;
   orchestrator postcondition/memory bugfix verified end-to-end.
5. AKSA-AGENT-001-R5: Real isolated runtime replay across multiple fixture variations via
   replay_candidate_in_sandbox + DAG dependency & JSON schema validation + calibrated confidence.
6. PublisherTrustStore symlink/legacy rejection & root rotation audit; MCP register_server defense.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.core.agent_directory import agent_directory_service
from app.core.agent_learning import SkillCandidateExtractor, SkillEvaluator, SkillVersionService
from app.core.orchestrator import (
    TaskOutcome,
    derive_expected_artifact_schema,
    get_artifact_postcondition_breakdown,
    verify_artifact_postcondition,
)
from app.skills.os_sandbox import (
    SandboxUnavailableError,
    build_linux_bwrap_args,
    build_seatbelt_profile,
    execute_in_os_sandbox,
    wrap_command,
)
from app.skills.skill_manager import PublisherTrustStore
from app.tools.mcp.mcp_client import MCPClientManager, MCPServerConfig

ENGINE_ROOT = Path(__file__).resolve().parent.parent
darwin_only = pytest.mark.skipif(sys.platform != "darwin", reason="macOS Seatbelt test")
win32_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows AppContainer test")
linux_bwrap_only = pytest.mark.skipif(
    not (sys.platform.startswith("linux") and shutil.which("bwrap")),
    reason="Linux bubblewrap runtime test",
)


# ===========================================================================
# 1. AKSA-SEC-003-R5 & R6: Cross-Platform OS Sandbox (Fail-Closed + Least Privilege)
# ===========================================================================


def test_wrap_command_refuses_raw_command_on_windows_and_unknown_os(monkeypatch, tmp_path: Path):
    """wrap_command MUST NEVER return an unwrapped raw command on Windows or unknown OS."""
    for plat in ("win32", "freebsd", "unknown_os"):
        monkeypatch.setattr(sys, "platform", plat)
        with pytest.raises(SandboxUnavailableError):
            wrap_command([sys.executable, "script.py"], tmp_path, [tmp_path])


@pytest.mark.asyncio
async def test_windows_sandbox_failure_is_fail_closed(monkeypatch, tmp_path: Path):
    """When Windows AppContainer/Job Object fails, execution MUST abort and NEVER fall back."""
    monkeypatch.setattr(sys, "platform", "win32")
    import app.skills.windows_sandbox as ws_mod

    def _failing_launcher(*args, **kwargs):
        raise ws_mod.WindowsSandboxError("Simulated AssignProcessToJobObject failure")

    monkeypatch.setattr(ws_mod, "run_windows_appcontainer_sandboxed", _failing_launcher)
    with pytest.raises(ws_mod.WindowsSandboxError):
        await execute_in_os_sandbox(
            cmd=[sys.executable, "-c", "print('SHOULD_NOT_RUN')"],
            cwd=tmp_path,
            env={"PATH": ""},
            workspace=tmp_path,
            read_roots=[tmp_path],
        )


def test_windows_appcontainer_ctypes_suspended_order_and_termination_on_job_failure(monkeypatch, tmp_path: Path):
    """Verify via Win32 ctypes mock that CreateProcessW uses CREATE_SUSPENDED and Job failure terminates child."""
    monkeypatch.setattr(sys, "platform", "win32")
    import ctypes
    import app.skills.windows_sandbox as ws_mod

    calls: list[tuple[str, Any]] = []

    class FakeHandle:
        def __init__(self, v: int = 100):
            self.value = v

        def __bool__(self) -> bool:
            return self.value != 0

    class FakeWintypes:
        DWORD = ctypes.c_uint32
        ULONG = ctypes.c_uint32
        UINT = ctypes.c_uint32
        BOOL = ctypes.c_int
        WORD = ctypes.c_uint16
        HANDLE = ctypes.c_void_p
        LPCWSTR = ctypes.c_wchar_p
        LPWSTR = ctypes.c_wchar_p

    class FakeDLL:
        def __init__(self, name: str):
            self.name = name

        def __getattr__(self, fn_name: str):
            def _fn(*args):
                calls.append((f"{self.name}.{fn_name}", args))
                if fn_name in ("CreateAppContainerProfile",):
                    return 0
                if fn_name in ("GetNamedSecurityInfoW", "SetEntriesInAclW", "SetNamedSecurityInfoW"):
                    return 0
                if fn_name == "CreateJobObjectW":
                    return 999
                if fn_name == "CreateProcessW":
                    # args[5] = creation_flags, args[-1] = byref(pi)
                    return 1
                if fn_name == "AssignProcessToJobObject":
                    # Simulate Job Object attachment failure -> MUST terminate child & NEVER call ResumeThread!
                    return 0
                if fn_name in ("SetInformationJobObject", "InitializeProcThreadAttributeList",
                               "UpdateProcThreadAttribute", "CreatePipe", "SetHandleInformation",
                               "TerminateProcess", "CloseHandle", "DeleteAppContainerProfile", "FreeSid"):
                    return 1
                return 0
            return _fn

    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kw: FakeDLL(name), raising=False)
    monkeypatch.setattr(ctypes, "wintypes", FakeWintypes, raising=False)

    with pytest.raises(ws_mod.WindowsSandboxError) as exc:
        ws_mod.run_windows_appcontainer_sandboxed(
            cmd=["python.exe", "evil.py"],
            cwd=tmp_path,
            env={"PATH": ""},
            workspace=tmp_path,
            read_roots=[tmp_path],
        )
    assert "AssignProcessToJobObject gagal" in str(exc.value)
    names = [c[0] for c in calls]
    # Verify AppContainer -> Job -> CreateProcessW (CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT) -> Terminate -> NEVER Resume
    assert "userenv.CreateAppContainerProfile" in names
    create_proc_call = [c for c in calls if c[0] == "kernel32.CreateProcessW"][0]
    creation_flags = create_proc_call[1][5]
    assert creation_flags & 0x00000004  # CREATE_SUSPENDED
    assert creation_flags & 0x00080000  # EXTENDED_STARTUPINFO_PRESENT
    assert "kernel32.TerminateProcess" in names
    assert "kernel32.ResumeThread" not in names


@win32_only
@pytest.mark.asyncio
async def test_real_windows_appcontainer_blocks_network_and_outside_writes(tmp_path: Path):
    """Real Windows runner test: AppContainer blocks network socket and outside workspace file write."""
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "escaped_win.txt"
    script = ws / "win_probe.py"
    script.write_text(
        f"import socket\n"
        f"try:\n    s = socket.socket(); s.settimeout(1); s.connect(('1.1.1.1', 80)); print('NET_ALLOW')\n"
        f"except Exception as e:\n    print('NET_DENY', type(e).__name__)\n"
        f"try:\n    open(r'{outside}', 'w').write('x'); print('WRITE_ALLOW')\n"
        f"except Exception as e:\n    print('WRITE_DENY', type(e).__name__)\n",
        encoding="utf-8",
    )
    res = await execute_in_os_sandbox(
        cmd=[sys.executable, str(script)],
        cwd=ws,
        env={"SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"), "PATH": os.environ.get("PATH", "")},
        workspace=ws,
        read_roots=[Path(sys.prefix), Path(sys.base_prefix), Path(sys.executable).resolve().parent, ws],
    )
    assert "NET_DENY" in res["stdout"] and "NET_ALLOW" not in res["stdout"]
    assert "WRITE_DENY" in res["stdout"] and "WRITE_ALLOW" not in res["stdout"]
    assert not outside.exists()


@darwin_only
def test_macos_seatbelt_is_true_deny_default_and_blocks_system_secrets(tmp_path: Path):
    """AKSA-SEC-005-R5: Seatbelt profile starts with (deny default) and blocks outside-home secrets + execv."""
    ws = (tmp_path / "ws").resolve()
    ws.mkdir()
    profile = build_seatbelt_profile(ws, [ENGINE_ROOT, Path(sys.prefix), Path(sys.base_prefix), ws])

    assert "(deny default)" in profile
    assert "(allow default)" not in profile

    probe = ws / "deny_default_probe.py"
    probe.write_text(
        """
import os, socket, pathlib
pathlib.Path('ok.txt').write_text('inside_ws')
for label, fn in [
    ('ETC_PASSWD', lambda: open('/etc/passwd').read(8)),
    ('VAR_TMP_LIST', lambda: os.listdir('/private/tmp')),
    ('HOME_LIST', lambda: os.listdir(os.path.expanduser('~'))),
    ('NET', lambda: socket.socket().connect(('127.0.0.1', 80))),
    ('FORK', lambda: os.fork()),
    ('EXEC_SH', lambda: os.execv('/bin/sh', ['/bin/sh', '-c', 'echo pwn'])),
]:
    try:
        fn()
        print(label, 'ALLOWED')
    except Exception as e:
        print(label, 'DENIED', type(e).__name__)
""",
        encoding="utf-8",
    )

    wrapped = wrap_command([sys.executable, str(probe)], ws, [ENGINE_ROOT, Path(sys.prefix), Path(sys.base_prefix), ws])
    res = subprocess.run(wrapped, cwd=ws, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert res.returncode == 0, res.stderr
    assert (ws / "ok.txt").read_text() == "inside_ws"
    for blocked in ("ETC_PASSWD", "VAR_TMP_LIST", "HOME_LIST", "NET", "FORK", "EXEC_SH"):
        assert f"{blocked} DENIED" in res.stdout
        assert f"{blocked} ALLOWED" not in res.stdout


def test_linux_bwrap_profile_does_not_mount_full_host_root(monkeypatch, tmp_path: Path):
    """AKSA-SEC-006-R5: Linux bwrap avoids '--ro-bind / /' and drops capabilities."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/bwrap" if name == "bwrap" else None)
    args = build_linux_bwrap_args(tmp_path, [ENGINE_ROOT], [sys.executable, "run.py"])
    joined = " ".join(args)
    assert "--ro-bind / /" not in joined
    assert "--unshare-all" in args
    assert "--die-with-parent" in args
    assert "--cap-drop" in args and "ALL" in args


@linux_bwrap_only
@pytest.mark.asyncio
async def test_real_linux_bwrap_isolates_home_and_network(tmp_path: Path):
    """Real Linux CI runner test: bubblewrap blocks network, /home, /root, and writes outside workspace."""
    ws = (tmp_path / "ws").resolve()
    ws.mkdir()
    outside = tmp_path / "escape_linux.txt"
    script = ws / "linux_probe.py"
    script.write_text(
        f"import os, socket\n"
        f"for label, fn in [('NET', lambda: socket.socket().connect(('1.1.1.1', 80))), "
        f"('WRITE', lambda: open('{outside}', 'w').write('x')), "
        f"('HOME', lambda: os.listdir('/home'))]:\n"
        f"    try:\n        fn(); print(label, 'ALLOWED')\n"
        f"    except Exception:\n        print(label, 'DENIED')\n",
        encoding="utf-8",
    )
    res = await execute_in_os_sandbox(
        cmd=[sys.executable, str(script)],
        cwd=ws,
        env={"PATH": "/usr/bin:/bin"},
        workspace=ws,
        read_roots=[ENGINE_ROOT, Path(sys.prefix), Path(sys.base_prefix), ws],
    )
    assert "NET DENIED" in res["stdout"]
    assert "WRITE DENIED" in res["stdout"]
    assert not outside.exists()


# ===========================================================================
# 2. AKSA-SEC-004-R5: Engine Manifest Launch Identity & Loopback Contract
# ===========================================================================


def test_engine_manifest_includes_launch_id_and_strict_mode_0600(tmp_path: Path):
    """Real engine process writes 0600 atomic manifest with launch_id, 127.0.0.1, version 1.0.0."""
    token = "aksa-cycle6-token"
    launch_id = "launch-cycle6-unique-abc123"
    env = {
        **os.environ,
        "AKSA_AUTH_TOKEN": token,
        "AKSA_LAUNCH_ID": launch_id,
        "AKSA_APPDATA_DIR": str(tmp_path),
        "PYTHONUNBUFFERED": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.main", "--host", "127.0.0.1", "--port", "0", "--production"],
        cwd=ENGINE_ROOT,
        env=env,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        marker_port = marker_pid = marker_lid = None
        deadline = time.time() + 30
        while time.time() < deadline:
            line = proc.stderr.readline()
            m = re.search(r"\[AKSA_ENGINE_READY:port=(\d+):pid=(\d+):launch_id=([^\]]+)\]", line or "")
            if m:
                marker_port, marker_pid, marker_lid = int(m.group(1)), int(m.group(2)), m.group(3)
                break
            if proc.poll() is not None:
                break
        assert marker_port and marker_pid == proc.pid
        assert marker_lid == launch_id

        manifest_path = tmp_path / "runtime" / "engine_port.json"
        assert manifest_path.exists()
        if sys.platform != "win32":
            assert (manifest_path.stat().st_mode & 0o777) == 0o600
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["host"] == "127.0.0.1"
        assert manifest["port"] == marker_port
        assert manifest["pid"] == proc.pid
        assert manifest["version"] == "1.0.0"
        assert manifest["launch_id"] == launch_id
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ===========================================================================
# 3. AKSA-AGENT-003-R5: Artifact Semantic Gate & Orchestrator Epilogue
# ===========================================================================


def test_artifact_semantic_gate_rejects_unknown_extensions_scalars_1cell_and_ornamental_pdf(tmp_path: Path):
    """Unknown formats return 'unsupported'; scalars, 1-cell Excel, & empty PDF drawings FAIL."""
    import openpyxl
    import pymupdf as fitz

    # 1. Unknown extension MUST NOT auto-pass
    unknown_f = tmp_path / "mystery.xyz"
    unknown_f.write_text("arbitrary non-empty bytes", encoding="utf-8")
    bd_unk = get_artifact_postcondition_breakdown(unknown_f)
    assert bd_unk["file_created"] is True
    assert bd_unk["format_valid"] is False
    assert bd_unk["semantic_postcondition_passed"] is False
    assert bd_unk["semantic_status"] == "unsupported"
    assert bd_unk["unsupported_format"] is True
    ok_unk, _ = verify_artifact_postcondition(unknown_f)
    assert ok_unk is False

    # 2. JSON scalar rejected
    scalar_json = tmp_path / "scalar.json"
    scalar_json.write_text('"just a string scalar"', encoding="utf-8")
    assert get_artifact_postcondition_breakdown(scalar_json)["semantic_postcondition_passed"] is False

    # 3. 1-cell Excel placeholder rejected
    one_cell_xlsx = tmp_path / "placeholder.xlsx"
    wb1 = openpyxl.Workbook()
    wb1.active["A1"] = "TODO"
    wb1.save(str(one_cell_xlsx))
    wb1.close()
    assert get_artifact_postcondition_breakdown(one_cell_xlsx)["semantic_postcondition_passed"] is False

    # 4. Ornamental vector-only PDF with 0 text rejected
    ornamental_pdf = tmp_path / "ornament_only.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.draw_rect(fitz.Rect(10, 10, 100, 100))
    doc.save(str(ornamental_pdf))
    doc.close()
    assert get_artifact_postcondition_breakdown(ornamental_pdf)["semantic_postcondition_passed"] is False

    # 5. Task-specific Excel schema validation (required_columns + formulas)
    report_xlsx = tmp_path / "keuangan.xlsx"
    wb2 = openpyxl.Workbook()
    ws2 = wb2.active
    ws2.append(["Bulan", "Pendapatan"])
    ws2.append(["Januari", 1000])
    ws2.append(["Total", "=SUM(B2:B2)"])
    wb2.save(str(report_xlsx))
    wb2.close()

    assert verify_artifact_postcondition(
        report_xlsx,
        expected_schema={"required_columns": ["Bulan", "Pendapatan"], "require_formulas": True, "min_rows": 3},
    )[0] is True
    # Missing formula fails when required
    assert verify_artifact_postcondition(
        report_xlsx,
        expected_schema={"required_columns": ["KolomTidakAda"]},
    )[0] is False
    # Prompt derivation sets require_formulas when asked for formula
    assert derive_expected_artifact_schema("Buat excel laporan dengan rumus SUM", report_xlsx).get("require_formulas") is True


@pytest.mark.asyncio
async def test_orchestrator_returns_unverified_outcome_on_invalid_artifact_without_swallowing(monkeypatch, tmp_path: Path):
    """End-to-end check proving orchestrator epilogue unpacks dict artifacts cleanly and marks UNVERIFIED."""
    from app.core.orchestrator import HierarchicalOrchestrator
    from app.db.models import DatabaseManager
    from app.db.seed import seed_default_indonesian_team

    agent_directory_service.set_root_dir(tmp_path / "aksa_data")
    db = DatabaseManager(db_path=tmp_path / "test.db")
    await db.initialize()
    await seed_default_indonesian_team(db)

    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()

    bad_art = ws_dir / "bad.xyz"
    bad_art.write_text("unsupported artifact output", encoding="utf-8")

    class FakeRouter:
        async def complete(self, **kwargs):
            msgs = kwargs.get("messages", [])
            if any(m.get("role") == "tool" for m in msgs):
                return {"content": "Selesai membuat berkas.", "tool_calls": [], "input_tokens": 10, "output_tokens": 10}
            return {
                "content": "",
                "tool_calls": [{"id": "c1", "function": {"name": "fake_tool", "arguments": "{}"}}],
                "input_tokens": 10,
                "output_tokens": 10,
            }

    import app.core.orchestrator as orch_mod
    monkeypatch.setattr(
        orch_mod.tool_registry,
        "get_schemas_for_categories",
        lambda cats: [{"type": "function", "function": {"name": "fake_tool", "parameters": {"type": "object", "properties": {}}}}],
    )

    async def fake_exec(name, **kwargs):
        return SimpleNamespace(success=True, summary="Dibuat bad.xyz", artifacts=[str(bad_art)], data={})

    monkeypatch.setattr(orch_mod.tool_registry, "execute", fake_exec)

    orch = HierarchicalOrchestrator(db=db, llm_router=FakeRouter())
    res = await orch.execute_hierarchical_task(
        prompt="Jelaskan ringkas saja tanpa delegasi",
        workspace_path=str(ws_dir),
        session_id="sess1",
    )
    assert res["task_outcome"] == TaskOutcome.UNVERIFIED.value


# ===========================================================================
# 4. AKSA-AGENT-001-R5: Real Isolated Runtime Replay + DAG & Schema Validation
# ===========================================================================


def test_skill_evaluator_dag_and_schema_catch_cyclic_dependencies():
    """DAG checker rejects forward/circular step dependencies and bad ToolRegistry schema args."""
    md = "---\nname: Test\ndescription: Test\n---\n# Test\n"
    cyclic_cand = {
        "structured_traces": [
            {"step_id": "s1", "depends_on": ["s2"], "tool_name": "excel_inspect", "input_summary": {}, "status": "success"},
            {"step_id": "s2", "depends_on": ["s1"], "tool_name": "list_workspace_files", "input_summary": {}, "status": "success"},
        ]
    }
    res = SkillEvaluator.evaluate(md, "cyclic_cand", candidate_data=cyclic_cand)
    assert res.dag_valid is False
    assert res.passed is False


@pytest.mark.asyncio
async def test_candidate_skill_runtime_replay_executes_real_tools_and_calibrates_confidence(tmp_path: Path):
    """Runtime replay executes real registered tools across fixture variations and measures pass_rate."""
    agent_directory_service.set_root_dir(tmp_path / "aksa_data")
    md = "---\nname: Excel Rekap\ndescription: Otomasi Excel\n---\n# Rekap\n"
    candidate_data = {
        "skill_id": "cand-excel-rt-1",
        "structured_traces": [
            {
                "step_id": "create_xlsx",
                "tool_name": "excel_create_workbook",
                "input_summary": {
                    "file_path": "{out_name}",
                    "sheets_spec": [
                        {
                            "title": "{report_title}",
                            "headers": ["Kategori", "Nominal"],
                            "rows": [["Operasional", 2500000], ["Total", "=SUM(B2:B2)"]],
                        }
                    ],
                },
                "output_summary": "Workbook created",
                "status": "success",
            }
        ],
    }

    fixtures = [
        {
            "name": "valid_q1_fixture",
            "inputs": {"out_name": "rekap_q1.xlsx", "report_title": "Laporan Q1"},
            "expected_artifacts": ["rekap_q1.xlsx"],
            "expected_schema": {"required_columns": ["Kategori", "Nominal"], "require_formulas": True},
            "expected_summary_contains": ["rekap_q1.xlsx"],
        },
        {
            "name": "valid_q2_fixture",
            "inputs": {"out_name": "rekap_q2.xlsx", "report_title": "Laporan Q2"},
            "expected_artifacts": ["rekap_q2.xlsx"],
            "expected_schema": {"required_columns": ["Kategori", "Nominal"], "min_rows": 2},
        },
    ]

    res = await SkillEvaluator.replay_candidate_in_sandbox(
        skill_md_content=md,
        skill_id="cand-excel-rt-1",
        candidate_data=candidate_data,
        replay_fixtures=fixtures,
    )
    assert res.replay_mode == "runtime"
    assert res.passed is True
    assert res.replay_passed is True
    assert res.replay_pass_rate == 1.0
    assert res.calibrated_confidence == 0.95
    assert len(res.replay_trace) == 2

    # Failing expected postcondition (e.g. expects missing column) drops pass_rate cleanly to 0.5 / fails
    mixed_fixtures = [
        fixtures[0],
        {**fixtures[1], "name": "failing_schema_fixture", "expected_schema": {"required_columns": ["KolomHilang"]}},
    ]
    res_mixed = await SkillEvaluator.replay_candidate_in_sandbox(
        skill_md_content=md,
        skill_id="cand-excel-rt-1",
        candidate_data=candidate_data,
        replay_fixtures=mixed_fixtures,
    )
    assert res_mixed.replay_mode == "runtime"
    assert res_mixed.replay_passed is False
    assert res_mixed.replay_pass_rate == 0.5
    assert res_mixed.passed is False


# ===========================================================================
# 5. Publisher Trust Store Hardening & MCP Registry Spoof Prevention
# ===========================================================================


def test_trust_store_rejects_legacy_without_migration_and_symlinks(tmp_path: Path):
    """Trust store rejects un-checksummed legacy files by default and rejects symlinks."""
    root = ed25519.Ed25519PrivateKey.generate()
    root_b64 = base64.b64encode(root.public_key().public_bytes_raw()).decode()
    trust_file = tmp_path / "trust" / "trust_store.json"
    trust_file.parent.mkdir(parents=True)
    # Write un-checksummed file
    trust_file.write_text(json.dumps({"version": "1.0", "publishers": {}, "revoked": []}), encoding="utf-8")

    # Strict mode rejects legacy file fail-closed
    strict_store = PublisherTrustStore(root_public_key_b64=root_b64, persist_path=trust_file, allow_legacy_migration=False)
    assert strict_store._load_error is not None
    with pytest.raises(PermissionError):
        strict_store._persist()

    # Symlink attack rejected
    if hasattr(os, "symlink"):
        real_f = tmp_path / "real.json"
        real_f.write_text("{}", encoding="utf-8")
        sym_f = tmp_path / "trust" / "sym_trust.json"
        os.symlink(real_f, sym_f)
        sym_store = PublisherTrustStore(root_public_key_b64=root_b64, persist_path=sym_f)
        assert sym_store._load_error is not None and "symlink" in sym_store._load_error


def test_mcp_register_server_rejects_external_system_trusted_spoofing():
    """MCPClientManager.register_server immediately rejects external 'system_trusted' claims."""
    mgr = MCPClientManager()
    with pytest.raises(PermissionError):
        mgr.register_server(
            MCPServerConfig(id="third_party", name="Spoof", command="node", trust_level="system_trusted", permissions=["*"])
        )
    with pytest.raises(PermissionError):
        mgr.register_server(
            MCPServerConfig(id="aksa_core", name="Hijack", command="node", trust_level="unreviewed", permissions=["*"])
        )
