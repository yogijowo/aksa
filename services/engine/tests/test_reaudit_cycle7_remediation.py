"""Cycle 7 Re-Audit Remediation & Security Verification Suite.

Covers all P1 and P2 findings from ``docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-7-2026-11-19.md``:
- P1-01: Windows AppContainer PROC_THREAD_ATTRIBUTE_HANDLE_LIST strict handle inheritance
- P1-02: Deterministic ToolRegistry.execute_replay boundary (no direct _handlers bypass)
- P1-03: Windows required vs optional read_roots ACL fail-closed + broad root rejection
- P2-01: Canonical path & symlink validation inside SkillEvaluator runtime replay
- P2-03: Structured pre-execution postcondition expectations & orthogonal semantic gates
- P2-04: Tightened Linux bwrap runtime subpaths + expanded isolation checks
"""

from __future__ import annotations

import ast
import ctypes
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from app.core.agent_directory import AgentIsolationError, agent_directory_service
from app.core.agent_learning import SkillEvaluator, resolve_replay_path
from app.core.orchestrator import (
    derive_expected_artifact_schema,
    get_artifact_postcondition_breakdown,
    verify_artifact_postcondition,
)
from app.core.sandbox import RiskLevel, SandboxManager, WorkspacePolicy, sandbox_manager
from app.skills.os_sandbox import (
    SandboxUnavailableError,
    build_linux_bwrap_args,
    build_seatbelt_profile,
    execute_in_os_sandbox,
)
from app.skills.windows_sandbox import (
    WindowsSandboxError,
    run_windows_appcontainer_sandboxed,
    validate_sandbox_read_root,
)
from app.tools.registry import REPLAY_ALLOWED_TOOLS, ToolResult, tool_registry

win32_only = pytest.mark.skipif(sys.platform != "win32", reason="Real Windows AppContainer runner test")
linux_bwrap_only = pytest.mark.skipif(
    not (sys.platform.startswith("linux") and shutil.which("bwrap")),
    reason="Real Linux bubblewrap runner test",
)


# ===========================================================================
# P1-01 & P1-03: Windows Handle Inheritance List & Strict Read-Roots ACLs
# ===========================================================================


def _make_win32_fake_env(
    monkeypatch,
    *,
    fail_acl_substring: str | None = None,
    succeed_job: bool = False,
):
    """Build deterministic Win32 ctypes mock environment for AppContainer security tests."""
    calls: list[tuple[str, tuple[Any, ...]]] = []

    class FakeWintypes:
        DWORD = ctypes.c_uint32
        ULONG = ctypes.c_uint32
        UINT = ctypes.c_uint32
        BOOL = ctypes.c_int
        WORD = ctypes.c_uint16
        HANDLE = ctypes.c_void_p
        LPCWSTR = ctypes.c_wchar_p
        LPWSTR = ctypes.c_wchar_p

    next_pipe_handle = 0x1000

    class FakeDLL:
        def __init__(self, name: str):
            self.name = name

        def __getattr__(self, fn_name: str):
            def _fn(*args):
                nonlocal next_pipe_handle
                calls.append((f"{self.name}.{fn_name}", args))
                if fn_name in ("CreateAppContainerProfile", "GetNamedSecurityInfoW", "SetEntriesInAclW"):
                    return 0
                if fn_name == "SetNamedSecurityInfoW":
                    # args[0] is unicode buffer for path_str
                    target = ""
                    try:
                        target = str(args[0].value if hasattr(args[0], "value") else args[0])
                    except Exception:
                        pass
                    if fail_acl_substring and fail_acl_substring in target:
                        return 5  # ERROR_ACCESS_DENIED
                    return 0
                if fn_name == "CreatePipe":
                    # Write distinct non-zero handle addresses into hRead (args[0]) and hWrite (args[1])
                    r_val = next_pipe_handle
                    w_val = next_pipe_handle + 4
                    next_pipe_handle += 0x10
                    ctypes.cast(args[0], ctypes.POINTER(ctypes.c_void_p))[0] = r_val
                    ctypes.cast(args[1], ctypes.POINTER(ctypes.c_void_p))[0] = w_val
                    return 1
                if fn_name == "CreateJobObjectW":
                    return 999
                if fn_name == "AssignProcessToJobObject":
                    return 1 if succeed_job else 0
                if fn_name in (
                    "SetInformationJobObject",
                    "InitializeProcThreadAttributeList",
                    "UpdateProcThreadAttribute",
                    "SetHandleInformation",
                    "CreateProcessW",
                    "TerminateProcess",
                    "TerminateJobObject",
                    "CloseHandle",
                    "DeleteAppContainerProfile",
                    "FreeSid",
                ):
                    return 1
                return 0

            return _fn

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kw: FakeDLL(name), raising=False)
    monkeypatch.setattr(ctypes, "wintypes", FakeWintypes, raising=False)
    return calls


def test_p1_01_windows_appcontainer_uses_explicit_handle_list_only_for_stdio_pipes(monkeypatch, tmp_path: Path):
    """Verify PROC_THREAD_ATTRIBUTE_HANDLE_LIST is configured strictly with stdout/stderr write pipe handles."""
    ws = tmp_path / "ws"
    ro = tmp_path / "ro"
    ws.mkdir()
    ro.mkdir()

    calls = _make_win32_fake_env(monkeypatch, succeed_job=False)

    with pytest.raises(WindowsSandboxError):
        run_windows_appcontainer_sandboxed(
            cmd=["python.exe", "script.py"],
            cwd=ws,
            env={"PATH": ""},
            workspace=ws,
            required_read_roots=[ro],
        )

    # 1. Attribute list MUST be initialized with count == 2 (SECURITY_CAPABILITIES + HANDLE_LIST)
    init_calls = [c[1] for c in calls if c[0] == "kernel32.InitializeProcThreadAttributeList"]
    assert init_calls, "InitializeProcThreadAttributeList harus dipanggil"
    assert all(args[1] == 2 for args in init_calls), "Attribute count harus 2"

    # 2. Pipes MUST have explicit SetHandleInformation calls: read=0, write=1
    set_inherit_calls = [c[1] for c in calls if c[0] == "kernel32.SetHandleInformation"]
    assert len(set_inherit_calls) == 4
    disabled = [int(args[0].value) for args in set_inherit_calls if args[2] == 0]
    enabled = [int(args[0].value) for args in set_inherit_calls if args[2] == 1]
    assert len(disabled) == 2 and len(enabled) == 2

    # 3. PROC_THREAD_ATTRIBUTE_HANDLE_LIST (0x00020002) MUST be updated strictly with the 2 write handles
    update_calls = [c[1] for c in calls if c[0] == "kernel32.UpdateProcThreadAttribute"]
    handle_list_updates = [args for args in update_calls if int(args[2]) == 0x00020002]
    assert len(handle_list_updates) == 1
    hl_array = handle_list_updates[0][3]
    hl_size = int(handle_list_updates[0][4])
    assert hl_size == 2 * ctypes.sizeof(ctypes.c_void_p)
    assert list(hl_array) == enabled

    # 4. Null stdin on STARTUPINFOW so no parent stdin handle leaks
    create_proc = [c[1] for c in calls if c[0] == "kernel32.CreateProcessW"][0]
    si_ex = create_proc[8]._obj
    assert not si_ex.StartupInfo.hStdInput


@win32_only
@pytest.mark.asyncio
async def test_p1_01_real_windows_child_cannot_inherit_unrelated_parent_handle(tmp_path: Path):
    """Real Windows CI check: extra inheritable parent file handle is NOT inherited into AppContainer child."""
    ws = tmp_path / "ws"
    ws.mkdir()
    secret = tmp_path / "parent_secret_handle.txt"
    secret.write_text("TOP_SECRET", encoding="utf-8")

    # Open an inheritable OS handle in parent process that AppContainer child must NOT inherit
    fd = os.open(str(secret), os.O_RDONLY)
    os.set_inheritable(fd, True)
    try:
        import msvcrt

        parent_handle = msvcrt.get_osfhandle(fd)
        probe = ws / "check_handle.py"
        probe.write_text(
            "import ctypes, sys\n"
            f"h = {int(parent_handle)}\n"
            "res = ctypes.windll.kernel32.GetFileSize(ctypes.c_void_p(h), None)\n"
            "err = ctypes.windll.kernel32.GetLastError()\n"
            "print('INHERITED' if res != 0xFFFFFFFF else f'BLOCKED:{err}')\n",
            encoding="utf-8",
        )
        res = await execute_in_os_sandbox(
            cmd=[sys.executable, str(probe)],
            cwd=ws,
            env={"PATH": os.environ.get("PATH", "")},
            workspace=ws,
            required_read_roots=[ws],
            optional_read_roots=[ENGINE_ROOT, Path(sys.prefix), Path(sys.base_prefix)],
        )
        assert "INHERITED" not in res["stdout"]
        assert "BLOCKED:" in res["stdout"]
    finally:
        os.close(fd)


def test_p1_03_rejects_overly_broad_read_roots_and_aborts_on_required_acl_failure(
    monkeypatch, caplog, tmp_path: Path
):
    """Broad roots (/, /Users, C:\\, C:\\Users, ~) and required ACL failures must abort fail-closed without path leaks."""
    for broad in (Path("/"), Path("/Users"), Path("/home"), Path.home(), Path("C:\\"), Path("C:\\Users")):
        with pytest.raises((WindowsSandboxError, PermissionError)):
            validate_sandbox_read_root(broad)

    ws = tmp_path / "ws"
    req_root = tmp_path / "req_missing_or_denied"
    ws.mkdir()
    req_root.mkdir()

    # Make Seatbelt & bwrap reject overly broad roots too
    with pytest.raises(PermissionError):
        build_seatbelt_profile(ws, [Path.home()])
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/bwrap" if name == "bwrap" else None)
    with pytest.raises(PermissionError):
        build_linux_bwrap_args(ws, [Path("/home")], [sys.executable, "run.py"])

    # Mock Windows: ACL fails on required root -> must fail closed BEFORE CreateProcessW
    calls = _make_win32_fake_env(monkeypatch, fail_acl_substring="req_missing_or_denied")
    with caplog.at_level(logging.WARNING, logger="aksa.sandbox.windows"):
        with pytest.raises(WindowsSandboxError) as exc:
            run_windows_appcontainer_sandboxed(
                cmd=["python.exe", "script.py"],
                cwd=ws,
                env={"PATH": ""},
                workspace=ws,
                required_read_roots=[req_root],
            )
    assert "ACL read/exec wajib" in str(exc.value)
    assert not any(c[0] == "kernel32.CreateProcessW" for c in calls)
    # Logs and exception must never leak the full parent user temp path
    assert str(tmp_path) not in str(exc.value)
    for rec in caplog.records:
        assert str(tmp_path) not in rec.getMessage()


def test_p1_03_optional_read_root_acl_failure_logs_redacted_summary(monkeypatch, caplog, tmp_path: Path):
    """Optional read_root failure does not abort execution setup but records safe redacted summary."""
    ws = tmp_path / "ws"
    req = tmp_path / "req_ok"
    opt = tmp_path / "opt_sys_dir"
    ws.mkdir()
    req.mkdir()
    opt.mkdir()

    # Succeed workspace & req, fail opt, fail AssignProcessToJobObject cleanly to end setup
    _make_win32_fake_env(monkeypatch, fail_acl_substring="opt_sys_dir", succeed_job=False)
    with caplog.at_level(logging.DEBUG, logger="aksa.sandbox.windows"):
        with pytest.raises(WindowsSandboxError) as exc:
            run_windows_appcontainer_sandboxed(
                cmd=["python.exe", "script.py"],
                cwd=ws,
                env={"PATH": ""},
                workspace=ws,
                required_read_roots=[req],
                optional_read_roots=[opt],
            )
    # Reached Job Object step instead of aborting on optional root ACL
    assert "AssignProcessToJobObject" in str(exc.value)
    msgs = [rec.getMessage() for rec in caplog.records]
    assert any("required_granted=1 optional_granted=0 optional_skipped=1" in m for m in msgs)
    assert all(str(tmp_path) not in m for m in msgs)


# ===========================================================================
# P1-02 & P2-01: Replay Registry Boundary, Canonical Path & Symlink Containment
# ===========================================================================


def test_p1_02_agent_learning_never_accesses_private_tool_handlers():
    """Static AST check: agent_learning.py must never access tool_registry._handlers."""
    src_path = ENGINE_ROOT / "app" / "core" / "agent_learning.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    private_handler_access = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "_handlers"
    ]
    assert private_handler_access == []


@pytest.mark.asyncio
async def test_p1_02_execute_replay_blocks_side_effectful_and_disallowed_tools(tmp_path: Path):
    """ToolRegistry.execute_replay rejects network/MCP, live computer-use, OS shell, memory writes, and bad sandboxes."""
    import app.tools  # noqa: F401

    ws = tmp_path / "replay_ws"
    ws.mkdir()
    other = tmp_path / "other_ws"
    other.mkdir()

    for dangerous_tool in (
        "invoke_mcp_tool",
        "capture_screen_and_a11y",
        "visual_screen_action",
        "control_live_office_app",
        "run_custom_python_task",
        "remember_user_fact",
        "recall_user_memories",
        "search_workspace_knowledge",
        "nonexistent_evil_tool",
    ):
        assert dangerous_tool not in REPLAY_ALLOWED_TOOLS
        res = await tool_registry.execute_replay(dangerous_tool, replay_workspace=ws)
        assert res.success is False
        assert "ditolak" in res.summary.lower() or "tidak ditemukan" in res.summary.lower()

    # Forbidden policy override params rejected even on allowlisted tools
    override_res = await tool_registry.execute_replay(
        "list_workspace_files",
        replay_workspace=ws,
        skip_approval=True,
    )
    assert override_res.success is False

    # Passing the global singleton or a multi-workspace sandbox MUST fail closed
    singleton_res = await tool_registry.execute_replay(
        "list_workspace_files",
        replay_workspace=ws,
        replay_sandbox=sandbox_manager,
        directory=".",
    )
    assert singleton_res.success is False

    multi_sandbox = SandboxManager(
        [
            WorkspacePolicy(folder_path=str(ws), allow_read=True, allow_write=True, allow_execute=False),
            WorkspacePolicy(folder_path=str(other), allow_read=True, allow_write=True, allow_execute=False),
        ]
    )
    multi_res = await tool_registry.execute_replay(
        "list_workspace_files",
        replay_workspace=ws,
        replay_sandbox=multi_sandbox,
        directory=".",
    )
    assert multi_res.success is False


@pytest.mark.asyncio
async def test_p1_02_replay_candidate_routes_via_execute_replay_and_rejects_side_effects(monkeypatch, tmp_path: Path):
    """SkillEvaluator.replay_candidate_in_sandbox uses execute_replay and rejects network/prod-state tools."""
    agent_directory_service.set_root_dir(tmp_path / "aksa_data")
    md = "---\nname: Side Effect Test\ndescription: Test\n---\n# Side Effect\n"

    # 1. Verify dangerous tool candidate is rejected fail-closed without executing handler
    dangerous_cand = {
        "skill_id": "cand-danger-1",
        "structured_traces": [
            {
                "step_id": "s1",
                "tool_name": "invoke_mcp_tool",
                "input_summary": {"server_id": "ext", "tool_name": "send_email", "arguments": {}},
                "status": "success",
            }
        ],
    }
    res_danger = await SkillEvaluator.replay_candidate_in_sandbox(
        skill_md_content=md,
        skill_id="cand-danger-1",
        candidate_data=dangerous_cand,
        replay_fixtures=[{"name": "f1", "inputs": {}}],
    )
    assert res_danger.passed is False
    assert res_danger.replay_passed is False

    # 2. Verify allowed tool calls execute_replay cleanly
    called_via_execute_replay: list[str] = []
    orig_exec_replay = tool_registry.execute_replay

    async def spy_execute_replay(name: str, replay_workspace: Path, **kwargs: Any) -> ToolResult:
        called_via_execute_replay.append(name)
        return await orig_exec_replay(name, replay_workspace=replay_workspace, **kwargs)

    monkeypatch.setattr(tool_registry, "execute_replay", spy_execute_replay)
    safe_cand = {
        "skill_id": "cand-safe-xlsx",
        "structured_traces": [
            {
                "step_id": "create_xlsx",
                "tool_name": "excel_create_workbook",
                "input_summary": {
                    "file_path": "{out_name}",
                    "sheets_spec": [{"title": "Data", "headers": ["A", "B"], "rows": [[1, 2], ["Sum", "=SUM(A2:B2)"]]}],
                },
                "status": "success",
            }
        ],
    }
    res_safe = await SkillEvaluator.replay_candidate_in_sandbox(
        skill_md_content=md,
        skill_id="cand-safe-xlsx",
        candidate_data=safe_cand,
        replay_fixtures=[{"name": "ok", "inputs": {"out_name": "ok.xlsx"}, "expected_artifacts": ["ok.xlsx"]}],
    )
    assert res_safe.passed is True
    assert called_via_execute_replay == ["excel_create_workbook"]


@pytest.mark.asyncio
async def test_p2_01_resolve_replay_path_blocks_traversal_and_symlinks(tmp_path: Path):
    """Canonical replay path validation rejects .. traversal, outside absolutes, and symlinks."""
    ws = (tmp_path / "ws").resolve()
    outside = (tmp_path / "outside").resolve()
    ws.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("SECRET", encoding="utf-8")

    # Traversal / escape attempts fail closed
    for evil in ("../outside/secret.txt", "sub/../../outside/secret.txt", str(outside / "secret.txt"), "\\\\evil\\share\\x"):
        with pytest.raises(AgentIsolationError):
            resolve_replay_path(evil, ws)

    # Symlink escape inside workspace fails closed
    if hasattr(os, "symlink"):
        os.symlink(outside / "secret.txt", ws / "link.xlsx")
        os.symlink(outside, ws / "symdir")
        with pytest.raises(AgentIsolationError):
            resolve_replay_path("link.xlsx", ws)
        with pytest.raises(AgentIsolationError):
            resolve_replay_path("symdir/escaped.xlsx", ws)

    # Valid path strictly under ws resolves canonically inside ws
    good = resolve_replay_path("subdir/report.xlsx", ws)
    assert good == ws / "subdir" / "report.xlsx"

    # Candidate attempting traversal inside nested/top-level replay arg MUST fail closed
    agent_directory_service.set_root_dir(tmp_path / "aksa_data_p201")
    md = "---\nname: Traversal Test\ndescription: Test\n---\n# Trav\n"
    traversal_cand = {
        "skill_id": "cand-trav-1",
        "structured_traces": [
            {
                "step_id": "s1",
                "tool_name": "excel_create_workbook",
                "input_summary": {
                    "file_path": "../escaped.xlsx",
                    "sheets_spec": [{"title": "X", "headers": ["A", "B"], "rows": [[1, 2]]}],
                },
                "status": "success",
            }
        ],
    }
    res = await SkillEvaluator.replay_candidate_in_sandbox(
        skill_md_content=md,
        skill_id="cand-trav-1",
        candidate_data=traversal_cand,
        replay_fixtures=[{"name": "trav", "inputs": {}}],
    )
    assert res.passed is False
    assert res.replay_passed is False
    assert not (tmp_path / "escaped.xlsx").exists()

    # Nested dict/list path escape attempts MUST also fail closed
    nested_cand = {
        "skill_id": "cand-trav-nested",
        "structured_traces": [
            {
                "step_id": "s1",
                "tool_name": "excel_create_workbook",
                "input_summary": {
                    "file_path": "ok.xlsx",
                    "sheets_spec": [{"title": "X", "extra": {"source_path": "../../etc/passwd"}}],
                },
                "status": "success",
            }
        ],
    }
    res_nested = await SkillEvaluator.replay_candidate_in_sandbox(
        skill_md_content=md,
        skill_id="cand-trav-nested",
        candidate_data=nested_cand,
        replay_fixtures=[{"name": "nested", "inputs": {}}],
    )
    assert res_nested.passed is False
    assert res_nested.replay_passed is False


def test_p2_02_engine_honors_per_launch_aksa_manifest_path(tmp_path: Path):
    """Sidecar honors AKSA_MANIFEST_PATH inside runtime dir with 0700 dir and 0600 manifest file (P2-02)."""
    import json
    import re
    import subprocess
    import time

    launch_id = "launch-p202-unique-xyz"
    runtime_dir = tmp_path / "runtime"
    target_manifest = runtime_dir / f"engine_port_{launch_id}.json"
    env = {
        **os.environ,
        "AKSA_AUTH_TOKEN": "aksa-p202-test-token",
        "AKSA_LAUNCH_ID": launch_id,
        "AKSA_APPDATA_DIR": str(tmp_path),
        "AKSA_MANIFEST_PATH": str(target_manifest),
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
        marker_lid = None
        deadline = time.time() + 30
        while time.time() < deadline:
            line = proc.stderr.readline()
            m = re.search(r"\[AKSA_ENGINE_READY:port=(\d+):pid=(\d+):launch_id=([^\]]+)\]", line or "")
            if m:
                marker_lid = m.group(3)
                break
            if proc.poll() is not None:
                break
        assert marker_lid == launch_id
        assert target_manifest.exists()
        assert not (runtime_dir / "engine_port.json").exists()
        if sys.platform != "win32":
            assert (runtime_dir.stat().st_mode & 0o777) == 0o700
            assert (target_manifest.stat().st_mode & 0o777) == 0o600
        data = json.loads(target_manifest.read_text(encoding="utf-8"))
        assert data["launch_id"] == launch_id
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ===========================================================================
# P2-03: Pre-Execution Task Postcondition Schema & Orthogonal Semantic Gates
# ===========================================================================


def test_p2_03_pre_execution_schema_and_orthogonal_gates_catch_wrong_content(tmp_path: Path):
    """format_valid + content_detected + task_requirement_satisfied are evaluated distinctly."""
    import docx
    import openpyxl

    # 1. Pre-execution prompt derivation extracts columns, formulas, min_rows
    xlsx_target = tmp_path / "gaji.xlsx"
    xlsx_schema = derive_expected_artifact_schema(
        "Buat rekap Excel dengan kolom: Nama, Jabatan, Gaji dengan rumus SUM minimal 4 baris.",
        xlsx_target,
    )
    assert xlsx_schema.get("require_formulas") is True
    assert xlsx_schema.get("min_rows") == 4
    assert [c.lower() for c in xlsx_schema.get("required_columns", [])] == ["nama", "jabatan", "gaji"]

    # Create valid non-empty 2x2 Excel WITHOUT required columns/formulas/rows
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Judul", "Catatan"])
    ws.append(["Biasa", "100"])
    wb.save(str(xlsx_target))
    wb.close()

    bd_wrong = get_artifact_postcondition_breakdown(xlsx_target, expected_schema=xlsx_schema)
    assert bd_wrong["file_created"] is True
    assert bd_wrong["format_valid"] is True
    assert bd_wrong["content_detected"] is True
    assert bd_wrong["task_requirement_satisfied"] is False
    assert bd_wrong["semantic_postcondition_passed"] is False

    # Now create Excel fulfilling EVERY derived task expectation
    wb2 = openpyxl.Workbook()
    ws2 = wb2.active
    ws2.append(["Nama", "Jabatan", "Gaji"])
    ws2.append(["Budi", "Analis", 5000000])
    ws2.append(["Sari", "Manajer", 9000000])
    ws2.append(["Total", "", "=SUM(C2:C3)"])
    wb2.save(str(xlsx_target))
    wb2.close()

    bd_ok = get_artifact_postcondition_breakdown(xlsx_target, expected_schema=xlsx_schema)
    assert bd_ok["format_valid"] is True
    assert bd_ok["content_detected"] is True
    assert bd_ok["task_requirement_satisfied"] is True
    assert bd_ok["semantic_postcondition_passed"] is True

    # 2. Word document section expectations derived pre-execution
    docx_target = tmp_path / "proposal.docx"
    docx_schema = derive_expected_artifact_schema(
        "Susun dokumen proposal dengan bagian: Ringkasan, Anggaran, Penutup minimal 3 paragraf.",
        docx_target,
    )
    assert [s.lower() for s in docx_schema.get("required_sections", [])] == ["ringkasan", "anggaran", "penutup"]
    assert docx_schema.get("min_paragraphs") == 3

    d = docx.Document()
    d.add_paragraph("Ringkasan proyek awal yang cukup panjang untuk lulus deteksi konten.")
    d.add_paragraph("Isi tambahan tanpa anggaran.")
    d.save(str(docx_target))

    ok_doc, msg_doc = verify_artifact_postcondition(docx_target, expected_schema=docx_schema)
    assert ok_doc is False
    assert "minimal" in msg_doc.lower() or "kurang" in msg_doc.lower() or "tidak ditemukan" in msg_doc.lower()


# ===========================================================================
# P2-04: Tightened Linux Bubblewrap Profile & Real Runtime Adversarial Tests
# ===========================================================================


def test_p2_04_linux_bwrap_excludes_broad_usr_and_usr_local(monkeypatch, tmp_path: Path):
    """bwrap mounts scoped /usr/bin, /usr/lib, etc., NEVER raw /usr (avoiding /usr/local) or /sbin."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/bwrap" if name == "bwrap" else None)
    ws = tmp_path / "ws"
    ws.mkdir()
    args = build_linux_bwrap_args(ws, [ENGINE_ROOT, Path("/usr")], [sys.executable, "run.py"])

    # Collect every bound source path after --ro-bind-try / --bind
    binds = []
    for i, tok in enumerate(args[:-1]):
        if tok in ("--ro-bind-try", "--ro-bind", "--bind"):
            binds.append(args[i + 1])

    assert "/usr" not in binds
    assert "/usr/local" not in binds
    assert "/sbin" not in binds
    assert "/home" not in binds
    assert "/etc/ssh" not in binds
    assert "--hostname" in args and "aksa-sandbox" in args


@linux_bwrap_only
@pytest.mark.asyncio
async def test_p2_04_real_linux_bwrap_blocks_network_proc_symlinks_and_traversal(tmp_path: Path):
    """Real Linux CI runner test: bwrap isolates network, /proc host PIDs, ../../ traversal, and symlinks."""
    ws = (tmp_path / "ws").resolve()
    ws.mkdir()
    outside_secret = tmp_path / "outside_secret.txt"
    outside_secret.write_text("OUTSIDE_HOST_DATA", encoding="utf-8")

    # Create a symlink inside workspace pointing outside workspace (kernel namespace won't mount outside target)
    escape_link = ws / "escape_link.txt"
    os.symlink(outside_secret, escape_link)

    probe = ws / "bwrap_adv.py"
    probe.write_text(
        f"import os, socket\n"
        f"# 1. External AF_INET socket\n"
        f"try:\n"
        f"    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1); s.connect(('1.1.1.1', 80)); print('INET ALLOWED')\n"
        f"except Exception:\n"
        f"    print('INET DENIED')\n"
        f"# 2. Traversal outside workspace\n"
        f"try:\n"
        f"    open('{ws}/../outside_secret.txt', 'r').read(); print('TRAV ALLOWED')\n"
        f"except Exception:\n"
        f"    print('TRAV DENIED')\n"
        f"# 3. Symlink escape outside workspace\n"
        f"try:\n"
        f"    open('{escape_link}', 'r').read(); print('SYMLINK ALLOWED')\n"
        f"except Exception:\n"
        f"    print('SYMLINK DENIED')\n"
        f"# 4. /proc PID isolation (host PID 1 from outside shouldn't expose arbitrary host cmdlines)\n"
        f"pids = [p for p in os.listdir('/proc') if p.isdigit()]\n"
        f"print('PROC_COUNT', len(pids))\n",
        encoding="utf-8",
    )
    res = await execute_in_os_sandbox(
        cmd=[sys.executable, str(probe)],
        cwd=ws,
        env={"PATH": "/usr/bin:/bin"},
        workspace=ws,
        required_read_roots=[ws],
        optional_read_roots=[ENGINE_ROOT, Path(sys.prefix), Path(sys.base_prefix), Path(sys.executable).resolve().parent],
    )
    assert res["exit_code"] == 0, res["stderr"]
    assert "INET DENIED" in res["stdout"]
    assert "TRAV DENIED" in res["stdout"]
    assert "SYMLINK DENIED" in res["stdout"]
    # Isolated PID namespace only sees tiny count of processes (bwrap + python <= 5)
    proc_line = [ln for ln in res["stdout"].splitlines() if ln.startswith("PROC_COUNT ")][0]
    assert int(proc_line.split()[1]) <= 6
